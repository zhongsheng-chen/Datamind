"""模型目录管理服务

负责维护模型及其版本的展示信息和说明。

核心功能：
  - update_model: 更新模型信息
  - update_version: 更新模型版本信息
"""

from typing import Any

from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    MetadataRepository,
    VersionRepository,
)
from datamind.services.mutation import MutationResult


class ModelCatalogService:
    """模型目录管理服务"""

    async def update_model(
            self,
            *,
            model_id: str,
            display_name: str | None = None,
            description: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """更新模型显示名称和描述"""
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            model = await metadata_repo.get_model(
                model_id=model_id,
            )

            if model is None:
                raise ValueError("模型不存在")

            before = {
                "display_name": model.display_name,
                "description": model.description,
            }
            model.display_name = display_name or None
            model.description = description or None
            model.updated_by = updated_by

            await uow.session.flush()
            await uow.session.refresh(model)

            result = {
                "model_id": model.model_id,
                "name": model.name,
                "display_name": model.display_name,
                "description": model.description,
                "updated_by": model.updated_by,
                "updated_at": model.updated_at,
            }
            return MutationResult.changed(
                result,
                before=before,
                after=result,
            )

    async def update_version(
            self,
            *,
            version_id: str,
            description: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """更新模型版本说明"""
        async with UnitOfWork() as uow:
            version_repo = VersionRepository(uow.session)
            model_version = await version_repo.get_version(
                version_id=version_id,
            )

            if model_version is None:
                raise ValueError("模型版本不存在")

            before = {"description": model_version.description}
            model_version.description = description or None
            model_version.updated_by = updated_by

            await uow.session.flush()
            await uow.session.refresh(model_version)

            result = {
                "version_id": model_version.version_id,
                "model_id": model_version.model_id,
                "version": model_version.version,
                "description": model_version.description,
                "status": model_version.status,
                "updated_by": model_version.updated_by,
                "updated_at": model_version.updated_at,
            }
            return MutationResult.changed(
                result,
                before=before,
                after=result,
            )
