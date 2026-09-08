"""模型生命周期管理服务

负责模型和版本的状态管理。

核心功能：
  - activate: 激活模型或指定版本
  - deactivate: 停用模型或模型版本
  - deprecate: 弃用模型或指定版本
  - archive: 归档模型或指定模型版本

使用示例：
  from datamind.services.lifecycle import ModelLifecycleService

  service = ModelLifecycleService()

  result = await service.activate(
      name="scorecard",
      version="1.0.0",
      updated_by="admin"
  )
"""

from typing import Any

import structlog

from datamind.db.core import UnitOfWork
from datamind.db.models import (
    Metadata,
    Version,
)
from datamind.db.repositories import (
    DeploymentRepository,
    MetadataRepository,
    VersionRepository,
)
from datamind.models.enums import MetadataStatus, VersionStatus
from datamind.models.errors import (
    InvalidModelStateError,
    VersionNotFoundError,
)
from datamind.models.guard import ModelGuard
from datamind.models.resolver import ModelResolver
from datamind.services.mutation import MutationResult

logger = structlog.get_logger(__name__)


class ModelLifecycleService:
    """模型生命周期管理服务

    负责模型元数据和模型版本的启用、停用等生命周期操作。
    """

    @staticmethod
    async def _resolve_model_and_version(
            *,
            resolver: ModelResolver,
            version_repo: VersionRepository,
            name: str | None,
            model_id: str | None,
            version: str | None,
            version_id: str | None,
    ) -> tuple[Metadata, Version | None]:
        """解析生命周期操作的模型和版本"""
        if version_id is not None and model_id is None and name is None:
            version_record = await version_repo.get_version(
                version_id
            )

            if version_record is None:
                raise VersionNotFoundError(
                    f"版本不存在: {version_id}"
                )

            model = await resolver.resolve_model(
                model_id=version_record.model_id,
            )

            return model, version_record

        model = await resolver.resolve_model(
            name=name,
            model_id=model_id,
        )

        if version is None and version_id is None:
            return model, None

        version_record = await resolver.resolve_version(
            model_id=model.model_id,
            version=version,
            version_id=version_id,
        )

        return model, version_record

    async def activate(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            updated_by: str = "system",
    ) -> MutationResult:
        """激活模型或指定模型版本

        如果指定 version 或 version_id，则激活指定版本和模型。
        如果未指定版本，则激活模型及其全部 inactive 版本。
        deprecated 和 archived 版本不受影响。

        参数：
            name: 模型名称
            model_id: 模型 ID
            version: 模型版本号
            version_id: 版本 ID
            updated_by: 操作人

        返回：
            激活结果及状态变更前后的审计快照

        异常：
            ValueError: 模型或版本不存在
            InvalidModelStateError: 没有可激活版本或状态不允许迁移
        """
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model, selected_version = (
                await self._resolve_model_and_version(
                    resolver=resolver,
                    version_repo=version_repo,
                    name=name,
                    model_id=model_id,
                    version=version,
                    version_id=version_id,
                )
            )

            resolved_version_id: str | None = None
            resolved_version: str | None = None
            resolved_version_status: str | None = None

            if selected_version is not None:
                versions_to_activate = [
                    selected_version
                ]
                resolved_version_id = (
                    selected_version.version_id
                )
                resolved_version = selected_version.version
            else:
                versions_to_activate = (
                    await version_repo.list_versions(
                        model_id=model.model_id,
                        status=VersionStatus.INACTIVE,
                    )
                )

                if not versions_to_activate:
                    active_versions = (
                        await version_repo.list_versions(
                            model_id=model.model_id,
                            status=VersionStatus.ACTIVE,
                            limit=1,
                        )
                    )

                    if not active_versions:
                        raise InvalidModelStateError(
                            "模型没有可激活版本"
                        )

            current_model_status = MetadataStatus(model.status)

            ModelGuard.validate_metadata_transition(
                current=current_model_status,
                target=MetadataStatus.ACTIVE,
            )

            for version_record in versions_to_activate:
                ModelGuard.validate_version_transition(
                    current=VersionStatus(
                        version_record.status
                    ),
                    target=VersionStatus.ACTIVE,
                )

            changed_versions = [
                version_record
                for version_record in versions_to_activate
                if VersionStatus(version_record.status) != VersionStatus.ACTIVE
            ]
            activated_version_count = len(changed_versions)
            before = {
                "model_status": model.status,
                "versions": [
                    {
                        "version_id": version_record.version_id,
                        "status": version_record.status,
                    }
                    for version_record in changed_versions
                ],
            }

            for version_record in versions_to_activate:
                version_record.status = VersionStatus.ACTIVE
                version_record.updated_by = updated_by

            if selected_version is not None:
                resolved_version_status = (
                    selected_version.status
                )

            model.status = MetadataStatus.ACTIVE
            model.updated_by = updated_by

            logger.info(
                "模型激活完成",
                model_id=model.model_id,
                name=model.name,
                model_status=model.status,
                version_id=resolved_version_id,
                version=resolved_version,
                version_status=resolved_version_status,
                activated_version_count=(
                    activated_version_count
                ),
                updated_by=updated_by,
            )

            result: dict[str, Any] = {
                "model_id": model.model_id,
                "name": model.name,
                "model_status": model.status,
                "version_id": resolved_version_id,
                "version": resolved_version,
                "version_status": resolved_version_status,
                "activated_version_count": (
                    activated_version_count
                ),
            }

            mutation = MutationResult.changed(
                result,
                before=before,
                after={
                    "model_status": model.status,
                    "versions": [
                        {
                            "version_id": version_record.version_id,
                            "status": version_record.status,
                        }
                        for version_record in changed_versions
                    ],
                },
            )

        return mutation

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

        如果指定 version 或 version_id，则停用指定版本。
        如果未指定版本，则停用模型及其全部 active 版本。
        deprecated 和 archived 版本不受影响。

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

            model, selected_version = (
                await self._resolve_model_and_version(
                    resolver=resolver,
                    version_repo=version_repo,
                    name=name,
                    model_id=model_id,
                    version=version,
                    version_id=version_id,
                )
            )

            resolved_version_id: str | None = None
            resolved_version: str | None = None
            resolved_version_status: str | None = None
            deactivated_version_count: int = 0

            if selected_version is not None:
                ver = selected_version

                active_deployments = await DeploymentRepository(
                    uow.session
                ).list_active_deployments(
                    model_id=model.model_id,
                    version_id=ver.version_id,
                )

                if active_deployments:
                    raise InvalidModelStateError(
                        "模型版本存在活动部署，请先禁用相关部署"
                    )

                current_version_status = VersionStatus(ver.status)

                active_versions = await version_repo.list_versions(
                    model_id=model.model_id,
                    status=VersionStatus.ACTIVE,
                )

                ModelGuard.validate_version_transition(
                    current=current_version_status,
                    target=VersionStatus.INACTIVE,
                )

                ver.status = VersionStatus.INACTIVE
                ver.updated_by = updated_by

                if current_version_status == VersionStatus.ACTIVE:
                    deactivated_version_count += 1

                resolved_version_id = ver.version_id
                resolved_version = ver.version
                resolved_version_status = ver.status

                has_other_active_version = any(
                    active_version.version_id
                    != ver.version_id
                    for active_version in active_versions
                )

                current_model_status = MetadataStatus(
                    model.status
                )

                if (
                        not has_other_active_version
                        and current_model_status
                        == MetadataStatus.ACTIVE
                ):

                    ModelGuard.validate_metadata_transition(
                        current=current_model_status,
                        target=MetadataStatus.INACTIVE,
                    )

                    model.status = MetadataStatus.INACTIVE
                    model.updated_by = updated_by

            else:
                active_deployments = await DeploymentRepository(
                    uow.session
                ).list_active_deployments(
                    model_id=model.model_id,
                )

                if active_deployments:
                    raise InvalidModelStateError(
                        "模型存在活动部署，请先禁用相关部署"
                    )

                current_model_status = MetadataStatus(model.status)

                active_versions = await version_repo.list_versions(
                    model_id=model.model_id,
                    status=VersionStatus.ACTIVE,
                )

                ModelGuard.validate_metadata_transition(
                    current=current_model_status,
                    target=MetadataStatus.INACTIVE,
                )

                for active_version in active_versions:
                    ModelGuard.validate_version_transition(
                        current=VersionStatus(
                            active_version.status
                        ),
                        target=VersionStatus.INACTIVE,
                    )

                for active_version in active_versions:
                    active_version.status = VersionStatus.INACTIVE
                    active_version.updated_by = updated_by
                    deactivated_version_count += 1

                model.status = MetadataStatus.INACTIVE
                model.updated_by = updated_by

            logger.info(
                "模型停用完成",
                model_id=model.model_id,
                name=model.name,
                model_status=model.status,
                version_id=resolved_version_id,
                version=resolved_version,
                version_status=resolved_version_status,
                deactivated_version_count=(
                    deactivated_version_count
                ),
                updated_by=updated_by,
            )

            result: dict[str, Any] = {
                "model_id": model.model_id,
                "name": model.name,
                "model_status": model.status,
                "version_id": resolved_version_id,
                "version": resolved_version,
                "version_status": resolved_version_status,
                "deactivated_version_count": (
                    deactivated_version_count
                ),
            }

        return result

    async def deprecate(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """弃用模型或指定模型版本

        如果指定 version 或 version_id，则弃用指定版本。
        如果未指定版本，则弃用模型及其全部 active、inactive 版本。
        deprecated 和 archived 版本不受影响。
        存在活动部署时拒绝弃用。

        参数：
            name: 模型名称
            model_id: 模型 ID
            version: 模型版本号
            version_id: 版本 ID
            updated_by: 操作人

        返回：
            弃用结果

        异常：
            ValueError: 模型或版本不存在
            InvalidModelStateError: 存在活动部署或状态不允许迁移
        """
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            deployment_repo = DeploymentRepository(
                uow.session
            )
            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model, selected_version = (
                await self._resolve_model_and_version(
                    resolver=resolver,
                    version_repo=version_repo,
                    name=name,
                    model_id=model_id,
                    version=version,
                    version_id=version_id,
                )
            )

            resolved_version_id: str | None = None
            resolved_version: str | None = None
            resolved_version_status: str | None = None
            deprecated_version_count: int = 0

            if selected_version is not None:
                version_record = selected_version
                active_deployments = (
                    await deployment_repo.list_active_deployments(
                        model_id=model.model_id,
                        version_id=version_record.version_id,
                    )
                )

                if active_deployments:
                    raise InvalidModelStateError(
                        "模型版本存在活动部署，请先禁用相关部署"
                    )

                active_versions = await version_repo.list_versions(
                    model_id=model.model_id,
                    status=VersionStatus.ACTIVE,
                )
                current_version_status = VersionStatus(
                    version_record.status
                )
                version_repo.deprecate_version(
                    version_record,
                    updated_by=updated_by,
                )

                if current_version_status in {
                    VersionStatus.ACTIVE,
                    VersionStatus.INACTIVE,
                }:
                    deprecated_version_count += 1

                has_other_active_version = any(
                    active_version.version_id
                    != version_record.version_id
                    for active_version in active_versions
                )
                current_model_status = MetadataStatus(
                    model.status
                )

                if (
                        not has_other_active_version
                        and current_model_status
                        == MetadataStatus.ACTIVE
                ):
                    ModelGuard.validate_metadata_transition(
                        current=current_model_status,
                        target=MetadataStatus.INACTIVE,
                    )
                    model.status = MetadataStatus.INACTIVE
                    model.updated_by = updated_by

                resolved_version_id = version_record.version_id
                resolved_version = version_record.version
                resolved_version_status = version_record.status
            else:
                active_deployments = (
                    await deployment_repo.list_active_deployments(
                        model_id=model.model_id,
                    )
                )

                if active_deployments:
                    raise InvalidModelStateError(
                        "模型存在活动部署，请先禁用相关部署"
                    )

                current_model_status = MetadataStatus(
                    model.status
                )
                model_versions = await version_repo.list_versions(
                    model_id=model.model_id,
                )
                versions_to_deprecate = [
                    model_version
                    for model_version in model_versions
                    if VersionStatus(model_version.status)
                    in {
                        VersionStatus.ACTIVE,
                        VersionStatus.INACTIVE,
                    }
                ]

                ModelGuard.validate_metadata_transition(
                    current=current_model_status,
                    target=MetadataStatus.DEPRECATED,
                )

                for model_version in versions_to_deprecate:
                    ModelGuard.validate_version_transition(
                        current=VersionStatus(
                            model_version.status
                        ),
                        target=VersionStatus.DEPRECATED,
                    )

                for model_version in versions_to_deprecate:
                    version_repo.deprecate_version(
                        model_version,
                        updated_by=updated_by,
                    )
                    deprecated_version_count += 1

                model.status = MetadataStatus.DEPRECATED
                model.updated_by = updated_by

            logger.info(
                "模型弃用完成",
                model_id=model.model_id,
                name=model.name,
                model_status=model.status,
                version_id=resolved_version_id,
                version=resolved_version,
                version_status=resolved_version_status,
                deprecated_version_count=(
                    deprecated_version_count
                ),
                updated_by=updated_by,
            )
            result: dict[str, Any] = {
                "model_id": model.model_id,
                "name": model.name,
                "model_status": model.status,
                "version_id": resolved_version_id,
                "version": resolved_version,
                "version_status": resolved_version_status,
                "deprecated_version_count": (
                    deprecated_version_count
                ),
            }

        return result

    async def archive(
            self,
            *,
            model_id: str | None = None,
            version_id: str | None = None,
            updated_by: str = "system",
    ) -> dict[str, Any]:
        """归档模型或指定模型版本

        指定 ``version_id`` 时仅归档该版本；指定 ``model_id`` 时归档
        模型及其全部 inactive、deprecated 版本。两种操作都会拒绝仍有
        活动部署的目标。
        """
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )
            model, version_record = await self._resolve_model_and_version(
                resolver=resolver,
                version_repo=version_repo,
                name=None,
                model_id=model_id,
                version=None,
                version_id=version_id,
            )

            if version_record is not None:
                active_deployments = (
                    await deployment_repo.list_active_deployments(
                        model_id=model.model_id,
                        version_id=version_record.version_id,
                    )
                )
                if active_deployments:
                    raise InvalidModelStateError(
                        "模型版本存在活动部署，请先禁用相关部署"
                    )

                version_repo.archive_version(
                    version_record,
                    updated_by=updated_by,
                )
                result = {
                    "model_id": model.model_id,
                    "name": model.name,
                    "model_status": model.status,
                    "version_id": version_record.version_id,
                    "version": version_record.version,
                    "version_status": version_record.status,
                    "archived_version_count": 1,
                }
            else:
                active_deployments = (
                    await deployment_repo.list_active_deployments(
                        model_id=model.model_id,
                    )
                )
                if active_deployments:
                    raise InvalidModelStateError(
                        "模型存在活动部署，请先禁用相关部署"
                    )

                model_versions = await version_repo.list_versions(
                    model_id=model.model_id,
                )
                versions_to_archive = [
                    item
                    for item in model_versions
                    if VersionStatus(item.status)
                    != VersionStatus.ARCHIVED
                ]
                ModelGuard.validate_metadata_transition(
                    current=MetadataStatus(model.status),
                    target=MetadataStatus.ARCHIVED,
                )
                for item in versions_to_archive:
                    ModelGuard.validate_version_transition(
                        current=VersionStatus(item.status),
                        target=VersionStatus.ARCHIVED,
                    )

                for item in versions_to_archive:
                    version_repo.archive_version(
                        item,
                        updated_by=updated_by,
                    )
                metadata_repo.archive_model(
                    model,
                    updated_by=updated_by,
                )
                result = {
                    "model_id": model.model_id,
                    "name": model.name,
                    "model_status": model.status,
                    "version_id": None,
                    "version": None,
                    "version_status": None,
                    "archived_version_count": len(versions_to_archive),
                }

        logger.info(
            "模型生命周期归档完成",
            **result,
            updated_by=updated_by,
        )
        return result
