# datamind/services/deleter.py

"""模型删除器

提供模型和版本的软删除与硬删除功能。

核心功能：
  - delete: 删除模型或版本（支持软删除和硬删除）

使用示例：
  from datamind.services.deleter import ModelDeleter

  deleter = ModelDeleter()

  # 软删除模型
  result = await deleter.delete(name="scorecard")

  # 硬删除模型
  result = await deleter.delete(name="scorecard", purge=True)

  # 删除指定版本
  result = await deleter.delete(name="scorecard", version="1.0.0")

  # 硬删除指定版本
  result = await deleter.delete(name="scorecard", version="1.0.0", purge=True)

  # 按 ID 删除
  result = await deleter.delete(model_id="mdl_a1b2c3d4")
"""

from datetime import datetime, timezone
from typing import Any

import bentoml
import structlog

from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import (
    MetadataPatch,
    MetadataRepository,
    VersionPatch,
    VersionRepository,
)
from datamind.models.enums import MetadataStatus, VersionStatus
from datamind.models.errors import ModelNotFoundError
from datamind.models.resolver import ModelResolver
from datamind.storage import get_storage

logger = structlog.get_logger(__name__)


class ModelDeleter:
    """模型删除器"""

    def __init__(self):
        self.storage = get_storage()

    async def delete(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            purge: bool = False,
            operator: str | None = None,
    ) -> dict[str, Any]:
        """删除模型或版本

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）
            version: 版本号（可选）
            version_id: 版本 ID（可选）
            purge: 是否硬删除，False 为软删除
            operator: 操作人（可选）

        返回：
            删除结果字典

        异常：
            ModelNotFoundError: 模型不存在
        """
        now = datetime.now(timezone.utc)

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_repo = MetadataRepository(session)
            version_repo = VersionRepository(session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            metadata = await resolver.resolve_model(
                model_id=model_id,
                name=name,
            )

            if not metadata:
                raise ModelNotFoundError("模型不存在")

            if version_id or version:
                target_version = await resolver.resolve_version(
                    model_id=metadata.model_id,
                    version_id=version_id,
                    version=version,
                )

                if not target_version:
                    raise ModelNotFoundError("模型版本不存在")

                logger.info(
                    "删除模型版本",
                    model_id=metadata.model_id,
                    version_id=target_version.version_id,
                    purge=purge,
                )

                if purge:
                    self._purge_version(target_version)

                version_repo.update_version(
                    target_version,
                    patch=VersionPatch(
                        deleted_at=now,
                        deleted_by=operator,
                    ),
                    updated_by=operator,
                )

                if target_version.status != VersionStatus.ARCHIVED:
                    version_repo.archive_version(
                        target_version,
                        updated_by=operator,
                    )

                return {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_id": target_version.version_id,
                    "version": target_version.version,
                    "action": "delete_version",
                    "purge": purge,
                }

            logger.info(
                "删除模型",
                model_id=metadata.model_id,
                purge=purge,
            )

            version_count = await self._purge_all_versions(
                session,
                metadata.model_id,
                purge=purge,
                deleted_at=now,
                operator=operator,
            )

            metadata_repo.update_model(
                metadata,
                patch=MetadataPatch(
                    deleted_at=now,
                    deleted_by=operator,
                ),
                updated_by=operator,
            )

            if metadata.status != MetadataStatus.ARCHIVED:
                metadata_repo.archive_model(
                    metadata,
                    updated_by=operator,
                )

            return {
                "model_id": metadata.model_id,
                "name": metadata.name,
                "version_count": version_count,
                "action": "delete_model",
                "purge": purge,
            }

        raise RuntimeError("删除操作失败")

    def _purge_version(
            self,
            version,
    ) -> None:
        """硬删除版本

        参数：
            version: 版本对象
        """
        # 删除存储文件
        for key in (
                version.model_key,
                version.input_schema_key,
                version.output_schema_key,
        ):
            if not key:
                continue

            try:
                self.storage.delete_by_key(
                    key=key,
                    strict=True,
                )

                logger.info(
                    "已删除存储文件",
                    key=key,
                )

            except Exception as exc:
                logger.error(
                    "删除存储文件失败",
                    key=key,
                    error=str(exc),
                )
                raise

        # 删除 BentoML 模型
        if not version.bento_tag:
            return

        try:
            for model in bentoml.models.list():
                if str(model.tag) == version.bento_tag:
                    bentoml.models.delete(model.tag)

                    logger.info(
                        "已删除 BentoML 模型",
                        tag=version.bento_tag,
                    )
                    break

        except Exception as exc:
            logger.error(
                "删除 BentoML 模型失败",
                tag=version.bento_tag,
                error=str(exc),
            )
            raise

    async def _purge_all_versions(
            self,
            session,
            model_id: str,
            *,
            purge: bool,
            deleted_at: datetime,
            operator: str | None = None,
    ) -> int:
        """硬删除模型的所有版本

        参数：
            session: 数据库会话
            model_id: 模型 ID
        """
        repo = VersionRepository(session)
        versions = await repo.list_versions(model_id=model_id)

        for version in versions:
            if purge:
                self._purge_version(version)

            repo.update_version(
                version,
                patch=VersionPatch(
                    deleted_at=deleted_at,
                    deleted_by=operator,
                ),
                updated_by=operator,
            )

            if version.status != VersionStatus.ARCHIVED:
                repo.archive_version(
                    version,
                    updated_by=operator,
                )

        return len(versions)
