# datamind/services/lifecycle.py

"""模型生命周期管理器

负责模型和版本的状态管理。

核心功能：
  - activate: 激活模型或指定版本
  - deactivate: 停用模型或指定版本

使用示例：
  from datamind.services.lifecycle import ModelLifecycle

  lifecycle = ModelLifecycle()

  result = await lifecycle.activate(
      name="scorecard",
      version="1.0.0",
      updated_by="admin"
  )
"""

from typing import Any

import structlog

from datamind.db.core import UnitOfWork
from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.enums import MetadataStatus, VersionStatus
from datamind.models.guard import ModelGuard
from datamind.models.resolver import ModelResolver

logger = structlog.get_logger(__name__)


class ModelLifecycle:
    """模型生命周期管理器

    负责模型元数据和模型版本的启用、停用等生命周期操作。
    """

    async def activate(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """激活模型或模型版本

        如果指定 version 或 version_id，则激活模型元数据和指定版本。
        如果只指定模型，则只激活模型元数据。

        参数：
            name: 模型名称
            model_id: 模型 ID
            version: 模型版本号
            version_id: 版本 ID
            updated_by: 操作人

        返回：
            激活结果

        异常：
            ValueError: 模型或版本不存在
            InvalidModelStateError: 状态不允许迁移
        """
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model = await resolver.resolve_model(
                name=name,
                model_id=model_id,
            )

            if not model:
                raise ValueError("模型不存在")

            current_model_status = MetadataStatus(model.status)

            ModelGuard.validate_metadata_transition(
                current=current_model_status,
                target=MetadataStatus.ACTIVE,
            )

            model.status = MetadataStatus.ACTIVE
            model.updated_by = updated_by

            ver = None

            if version or version_id:
                ver = await resolver.resolve_version(
                    model_id=model.model_id,
                    version=version,
                    version_id=version_id,
                )

                if not ver:
                    raise ValueError("模型版本不存在")

                current_version_status = VersionStatus(ver.status)

                ModelGuard.validate_version_transition(
                    current=current_version_status,
                    target=VersionStatus.ACTIVE,
                )

                ver.status = VersionStatus.ACTIVE
                ver.updated_by = updated_by

            logger.info(
                "模型激活完成",
                model_id=model.model_id,
                name=model.name,
                model_status=model.status,
                version_id=ver.version_id if ver else None,
                version=ver.version if ver else None,
                version_status=ver.status if ver else None,
                updated_by=updated_by,
            )

            return {
                "model_id": model.model_id,
                "name": model.name,
                "model_status": model.status,
                "version_id": ver.version_id if ver else None,
                "version": ver.version if ver else None,
                "version_status": ver.status if ver else None,
            }

        raise RuntimeError("模型激活失败：事务未正常完成")

    async def deactivate(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """停用模型或模型版本

        如果指定 version 或 version_id，则只停用指定版本。
        如果只指定模型，则停用模型元数据。

        参数：
            name: 模型名称
            model_id: 模型 ID
            version: 模型版本号
            version_id: 版本 ID
            updated_by: 操作人

        返回：
            停用结果

        异常：
            ValueError: 模型或版本不存在
            InvalidModelStateError: 状态不允许迁移
        """
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model = await resolver.resolve_model(
                name=name,
                model_id=model_id,
            )

            if not model:
                raise ValueError("模型不存在")

            ver = None

            if version or version_id:
                ver = await resolver.resolve_version(
                    model_id=model.model_id,
                    version=version,
                    version_id=version_id,
                )

                if not ver:
                    raise ValueError("模型版本不存在")

                current_version_status = VersionStatus(ver.status)

                ModelGuard.validate_version_transition(
                    current=current_version_status,
                    target=VersionStatus.INACTIVE,
                )

                ver.status = VersionStatus.INACTIVE
                ver.updated_by = updated_by

            else:
                current_model_status = MetadataStatus(model.status)

                ModelGuard.validate_metadata_transition(
                    current=current_model_status,
                    target=MetadataStatus.INACTIVE,
                )

                model.status = MetadataStatus.INACTIVE
                model.updated_by = updated_by

            logger.info(
                "模型停用完成",
                model_id=model.model_id,
                name=model.name,
                model_status=model.status,
                version_id=ver.version_id if ver else None,
                version=ver.version if ver else None,
                version_status=ver.status if ver else None,
                updated_by=updated_by,
            )

            return {
                "model_id": model.model_id,
                "name": model.name,
                "model_status": model.status,
                "version_id": ver.version_id if ver else None,
                "version": ver.version if ver else None,
                "version_status": ver.status if ver else None,
            }

        raise RuntimeError("模型停用失败：事务未正常完成")
