# datamind/services/deletion.py

"""模型删除服务

将可恢复的逻辑删除、恢复和不可逆制品清理分成三个明确操作。

核心功能：
  - delete: 逻辑删除模型或版本
  - restore: 恢复逻辑删除的模型或版本
  - purge: 永久清理已逻辑删除对象的物理制品

使用示例：
  from datamind.services.deletion import ModelDeletionService

  service = ModelDeletionService()

  await service.delete(
      name="scorecard",
      reason="版本停用",
  )
  await service.restore(
      name="scorecard",
  )
  await service.purge(
      name="scorecard",
      reason="超过保留期",
  )
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from typing import Any

import bentoml
import structlog

from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import (
    ArtifactRepository,
    DeploymentRepository,
    MetadataRepository,
    RuntimeRepository,
    VersionRepository,
)
from datamind.models.enums import (
    ArtifactStatus,
)
from datamind.models.errors import InvalidModelStateError
from datamind.models.resolver import ModelResolver
from datamind.storage import get_storage
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _ArtifactTarget:
    """一次物理清理所需的制品快照"""

    artifact_id: str
    model_key: str
    input_schema_key: str | None
    output_schema_key: str | None
    bento_tag: str


class ModelDeletionService:
    """模型删除、恢复和制品清理服务"""

    def __init__(self) -> None:
        """初始化模型删除服务"""
        self.storage = get_storage()

    async def delete(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            reason: str | None = None,
            operator: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除模型或版本

        删除会保留数据库记录和物理制品，且拒绝删除仍有活动部署的对象。
        删除整个模型时，同一删除批次中的版本会使用相同 deletion_id。
        """
        now = datetime.now(timezone.utc)
        deletion_id = generate_random_id(
            prefix="del"
        )
        target_version = (
            version_id is not None
            or version is not None
        )

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            resolver = ModelResolver(
                metadata_repo,
                version_repo,
            )
            metadata = await resolver.resolve_model(
                model_id=model_id,
                name=name,
            )

            result: dict[str, Any]

            if target_version:
                target = await resolver.resolve_version(
                    model_id=metadata.model_id,
                    version_id=version_id,
                    version=version,
                    include_archived=True,
                )
                await self._ensure_no_active_deployments(
                    deployment_repo,
                    model_id=metadata.model_id,
                    version_id=target.version_id,
                )
                version_repo.mark_deleted(
                    target,
                    deleted_at=now,
                    deleted_by=operator,
                    deletion_id=deletion_id,
                    deletion_reason=reason,
                )

                result = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_id": target.version_id,
                    "version": target.version,
                    "deletion_id": target.deletion_id,
                    "action": "delete_version",
                }

            else:
                await self._ensure_no_active_deployments(
                    deployment_repo,
                    model_id=metadata.model_id,
                )
                versions = await version_repo.list_versions(
                    model_id=metadata.model_id,
                    include_archived=True,
                )

                for item in versions:
                    version_repo.mark_deleted(
                        item,
                        deleted_at=now,
                        deleted_by=operator,
                        deletion_id=deletion_id,
                        deletion_reason=reason,
                    )

                metadata_repo.mark_deleted(
                    metadata,
                    deleted_at=now,
                    deleted_by=operator,
                    deletion_id=deletion_id,
                    deletion_reason=reason,
                )

                result = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_count": len(versions),
                    "deletion_id": metadata.deletion_id,
                    "action": "delete_model",
                }

        return result

    async def restore(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            operator: str | None = None,
    ) -> dict[str, Any]:
        """恢复尚未永久清理的逻辑删除模型或版本"""
        target_version = (
            version_id is not None
            or version is not None
        )

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            artifact_repo = ArtifactRepository(uow.session)
            resolver = ModelResolver(
                metadata_repo,
                version_repo,
            )
            metadata = await resolver.resolve_model(
                model_id=model_id,
                name=name,
            )

            result: dict[str, Any]

            if target_version:
                if metadata.deleted_at is not None:
                    raise InvalidModelStateError(
                        "模型已被整体删除，请先恢复模型"
                    )

                target = await resolver.resolve_version(
                    model_id=metadata.model_id,
                    version_id=version_id,
                    version=version,
                    include_archived=True,
                )
                await self._ensure_version_restorable(
                    artifact_repo,
                    target,
                )
                version_repo.restore_version(
                    target,
                    restored_by=operator,
                )

                result = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_id": target.version_id,
                    "version": target.version,
                    "action": "restore_version",
                }

            else:
                if metadata.deleted_at is None:
                    raise InvalidModelStateError(
                        "模型未被逻辑删除"
                    )

                deletion_id = metadata.deletion_id
                versions = await version_repo.list_versions(
                    model_id=metadata.model_id,
                    include_archived=True,
                )
                restored_count = 0

                for item in versions:
                    if item.deletion_id != deletion_id:
                        continue

                    await self._ensure_version_restorable(
                        artifact_repo,
                        item,
                    )
                    version_repo.restore_version(
                        item,
                        restored_by=operator,
                    )
                    restored_count += 1

                metadata_repo.restore_model(
                    metadata,
                    restored_by=operator,
                )

                result = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_count": restored_count,
                    "action": "restore_model",
                }

        return result

    async def purge(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
            version: str | None = None,
            version_id: str | None = None,
            reason: str,
            operator: str | None = None,
    ) -> dict[str, Any]:
        """永久清理已逻辑删除对象的全部物理制品

        清理前先将数据库状态持久化为 purge_pending。每个制品的成功或
        失败结果随后独立写回，因此进程异常退出后可再次调用本方法重试。
        """
        if not reason.strip():
            raise ValueError(
                "永久清理必须提供原因"
            )

        target_info, targets = await self._request_purge(
            model_id=model_id,
            name=name,
            version=version,
            version_id=version_id,
            reason=reason,
            operator=operator,
        )
        errors: list[dict[str, str]] = []

        for target in targets:
            try:
                self._purge_artifact(target)
            except Exception as exc:
                error = str(exc)
                await self._record_purge_result(
                    artifact_id=target.artifact_id,
                    error=error,
                    operator=operator,
                )
                errors.append({
                    "artifact_id": target.artifact_id,
                    "error": error,
                })
            else:
                await self._record_purge_result(
                    artifact_id=target.artifact_id,
                    error=None,
                    operator=operator,
                )

        return {
            **target_info,
            "reason": reason,
            "artifact_count": len(targets),
            "purged_count": len(targets) - len(errors),
            "failed_count": len(errors),
            "errors": errors,
            "action": (
                "purge_failed"
                if errors
                else "purge_completed"
            ),
        }

    async def _request_purge(
            self,
            *,
            model_id: str | None,
            name: str | None,
            version: str | None,
            version_id: str | None,
            reason: str,
            operator: str | None,
    ) -> tuple[dict[str, Any], list[_ArtifactTarget]]:
        """持久化清理请求并返回待清理制品快照"""
        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            artifact_repo = ArtifactRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            runtime_repo = RuntimeRepository(uow.session)
            resolver = ModelResolver(
                metadata_repo,
                version_repo,
            )
            metadata = await resolver.resolve_model(
                model_id=model_id,
                name=name,
            )
            info: dict[str, Any]

            if version_id is not None or version is not None:
                target_version = await resolver.resolve_version(
                    model_id=metadata.model_id,
                    version_id=version_id,
                    version=version,
                    include_archived=True,
                )

                if target_version.deleted_at is None:
                    raise InvalidModelStateError(
                        "模型版本必须先逻辑删除才能永久清理"
                    )

                await self._ensure_purge_safe(
                    deployment_repo,
                    runtime_repo,
                    model_id=metadata.model_id,
                    version_id=target_version.version_id,
                )
                versions = [target_version]
                info = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_id": target_version.version_id,
                    "version": target_version.version,
                }
            else:
                if metadata.deleted_at is None:
                    raise InvalidModelStateError(
                        "模型必须先逻辑删除才能永久清理"
                    )

                await self._ensure_purge_safe(
                    deployment_repo,
                    runtime_repo,
                    model_id=metadata.model_id,
                )
                versions = await version_repo.list_versions(
                    model_id=metadata.model_id,
                    include_archived=True,
                )
                info = {
                    "model_id": metadata.model_id,
                    "name": metadata.name,
                    "version_count": len(versions),
                }

            targets: list[_ArtifactTarget] = []

            for item in versions:
                all_artifacts = await artifact_repo.list_artifacts(
                    version_id=item.version_id,
                    include_purged=True,
                    for_update=True,
                )

                if not all_artifacts:
                    raise InvalidModelStateError(
                        "模型版本缺少制品记录，不能确认永久清理状态: "
                        f"{item.version_id}"
                    )

                for artifact in all_artifacts:
                    if artifact.status == str(ArtifactStatus.PURGED):
                        continue

                    artifact_repo.request_purge(
                        artifact,
                        reason=reason,
                        requested_by=operator,
                    )
                    targets.append(_ArtifactTarget(
                        artifact_id=artifact.artifact_id,
                        model_key=artifact.model_key,
                        input_schema_key=artifact.input_schema_key,
                        output_schema_key=artifact.output_schema_key,
                        bento_tag=artifact.bento_tag,
                    ))

        return info, targets

    @staticmethod
    async def _record_purge_result(
            *,
            artifact_id: str,
            error: str | None,
            operator: str | None,
    ) -> None:
        """持久化单个制品的清理结果"""
        async with UnitOfWork() as uow:
            repository = ArtifactRepository(uow.session)
            artifact = await repository.get_artifact(
                artifact_id,
                for_update=True,
            )

            if artifact is None:
                raise RuntimeError(
                    f"清理结果对应的制品不存在: {artifact_id}"
                )

            if error is None:
                repository.mark_purged(
                    artifact,
                    purged_by=operator,
                )
            else:
                repository.mark_purge_failed(
                    artifact,
                    error=error,
                )

    def _purge_artifact(
            self,
            target: _ArtifactTarget,
    ) -> None:
        """幂等清理单个物理制品"""
        for key in (
                target.model_key,
                target.input_schema_key,
                target.output_schema_key,
        ):
            if key is not None:
                self.storage.delete_by_key(
                    key=key,
                    strict=False,
                )

        for model in bentoml.models.list():
            if str(model.tag) == target.bento_tag:
                bentoml.models.delete(model.tag)
                break

    @staticmethod
    async def _ensure_no_active_deployments(
            repository: DeploymentRepository,
            *,
            model_id: str,
            version_id: str | None = None,
    ) -> None:
        """确认对象不存在活动部署"""
        deployments = await repository.list_active_deployments(
            model_id=model_id,
            version_id=version_id,
        )

        if deployments:
            raise InvalidModelStateError(
                "模型或版本存在活动部署，请先禁用相关部署"
            )

    @classmethod
    async def _ensure_purge_safe(
            cls,
            deployment_repo: DeploymentRepository,
            runtime_repo: RuntimeRepository,
            *,
            model_id: str,
            version_id: str | None = None,
    ) -> None:
        """确认对象不存在活动部署或加载中的运行实例"""
        await cls._ensure_no_active_deployments(
            deployment_repo,
            model_id=model_id,
            version_id=version_id,
        )
        runtimes = await runtime_repo.list_runtimes(
            model_id=model_id,
            version_id=version_id,
        )

        if any(
                runtime.status in {"loading", "loaded"}
                for runtime in runtimes
        ):
            raise InvalidModelStateError(
                "模型或版本仍有加载中的运行实例，不能永久清理"
            )

    @staticmethod
    async def _ensure_version_restorable(
            repository: ArtifactRepository,
            version_record: Any,
    ) -> None:
        """确认版本已删除且当前制品仍完整"""
        if version_record.deleted_at is None:
            raise InvalidModelStateError(
                "模型版本未被逻辑删除"
            )

        artifact = await repository.get_current_artifact(
            version_record.version_id
        )

        if artifact is None or artifact.status != str(ArtifactStatus.ACTIVE):
            raise InvalidModelStateError(
                "模型版本的当前制品不存在或已进入永久清理流程"
            )
