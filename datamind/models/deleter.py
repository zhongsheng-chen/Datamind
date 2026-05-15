# datamind/models/deleter.py

"""模型删除器

提供模型和版本的软删除与硬删除功能。

核心功能：
  - delete: 删除模型或版本（支持软删除和硬删除）

使用示例：
  from datamind.models.deleter import ModelDeleter

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
from typing import Any

import structlog
import bentoml

from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import VersionRepository
from datamind.models.enums import MetadataStatus, VersionStatus
from datamind.models.errors import ModelNotFoundError
from datamind.models.resolver import ModelResolver
from datamind.storage import get_storage

logger = structlog.get_logger(__name__)


class ModelDeleter:
    """模型删除器"""

    def __init__(self):
        self.storage = get_storage()
        self.resolver = ModelResolver()

    async def delete(
        self,
        *,
        model_id: str | None = None,
        name: str | None = None,
        version: str | None = None,
        version_id: str | None = None,
        purge: bool = False,
    ) -> dict[str, str | bool | Any] | None:
        """删除模型或版本

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）
            version: 版本号（可选）
            version_id: 版本 ID（可选）
            purge: 是否硬删除，False 为软删除（归档）

        返回：
            删除结果字典

        异常：
            ModelNotFoundError: 模型不存在
        """
        async with UnitOfWork() as uow:
            session = uow.session

            metadata = await self.resolver.resolve_model(
                session,
                model_id=model_id,
                name=name,
            )

            if not metadata:
                raise ModelNotFoundError("模型不存在")

            target_version = await self.resolver.resolve_version(
                session,
                model_id=metadata.model_id,
                version_id=version_id,
                version=version,
            )

            if target_version:
                logger.info(
                    "删除版本",
                    model_id=metadata.model_id,
                    version_id=target_version.version_id,
                    purge=purge,
                )

                if purge:
                    self._purge_version(target_version)

                target_version.status = VersionStatus.ARCHIVED

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

            if purge:
                await self._purge_all_versions(session, metadata.model_id)

            metadata.status = MetadataStatus.ARCHIVED

            return {
                "model_id": metadata.model_id,
                "name": metadata.name,
                "action": "delete_model",
                "purge": purge,
            }
        return None

    def _purge_version(self, version) -> None:
        """硬删除版本

        参数：
            version: 版本对象
        """
        # 删除存储文件
        if version.storage_key:
            self.storage.delete_by_key(
                key=version.storage_key,
                strict=True
            )
            logger.info("已删除存储文件", storage_key=version.storage_key)

        # 删除 BentoML 模型
        for m in bentoml.models.list():
            if str(m.tag) == version.bento_tag:
                bentoml.models.delete(m.tag)
                logger.info("已删除BentoML模型", tag=str(m.tag))
                break

    async def _purge_all_versions(self, session, model_id: str) -> None:
        """硬删除模型的所有版本

        参数：
            session: 数据库会话
            model_id: 模型 ID
        """
        repo = VersionRepository(session)
        versions = await repo.list_versions(model_id)

        for v in versions:
            self._purge_version(v)
            v.status = VersionStatus.ARCHIVED