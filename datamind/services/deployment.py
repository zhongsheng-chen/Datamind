"""模型部署服务

负责模型部署的创建、状态迁移与逻辑删除。

核心功能：
  - create_deployment: 创建部署实例
  - enable_deployment: 启用部署
  - disable_deployment: 禁用部署
  - delete_deployment: 逻辑删除部署
  - restore_deployment: 恢复部署

使用示例：
  from datamind.services.deployment import DeploymentLifecycleService

  service = DeploymentLifecycleService()

  # 创建分类模型部署
  result = await service.create_deployment(
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      environment="production",
      threshold=0.5,
      deployed_by="system"
  )

  # 创建评分卡模型部署
  result = await service.create_deployment(
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      environment="production",
      threshold=600.0,
      deployed_by="system"
  )
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from datamind.config import get_settings
from datamind.config.classification import ClassificationConfig
from datamind.config.scoring import ScoringConfig
from datamind.constants import (
    Environment,
    Framework,
)
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    ControlRepository,
    DeploymentPatch,
    DeploymentRepository,
    ExperimentRepository,
    MetadataRepository,
    RoutingPatch,
    RoutingRepository,
    RuntimeRepository,
    VariantRepository,
    VersionRepository,
)
from datamind.models.enums import (
    DeploymentRole,
    DeploymentStatus,
    ExperimentStatus,
    ExperimentVariantStatus,
    MetadataStatus,
    RolloutType,
    RuntimeControlStatus,
    VersionStatus,
)
from datamind.models.errors import (
    DeploymentError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    ModelNotFoundError,
    VersionNotFoundError,
)
from datamind.services.mutation import MutationResult
from datamind.models.guard import ModelGuard
from datamind.models.resolver import ModelResolver
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


class DeploymentLifecycleService:
    """模型部署服务"""

    async def create_deployment(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version_id: str | None = None,
            version: str | None = None,
            environment: str = "production",
            rollout_type: str = RolloutType.FULL.value,
            role: str = DeploymentRole.CHAMPION.value,
            threshold: float | None = None,
            description: str | None = None,
            deployed_by: str | None = None,
    ) -> dict[str, Any]:
        """创建部署

        参数：
            name: 模型名称（可选）
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            version: 版本号（可选）
            environment: 部署环境
            rollout_type: 发布类型
            role: 部署角色
            threshold: 决策阈值（可选）
            description: 部署说明（可选）
            deployed_by: 部署人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status
        """
        normalized_rollout_type = (
            rollout_type.strip().lower()
        )
        normalized_role = role.strip().lower()

        self.validate_release_mode(
            rollout_type=normalized_rollout_type,
            role=normalized_role,
        )

        deployment_id = generate_random_id(
            prefix="dep"
        )

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            try:
                model = await resolver.resolve_model(
                    model_id=model_id,
                    name=name,
                )
            except ModelNotFoundError as exc:
                raise DeploymentError(
                    str(exc)
                ) from exc

            ModelGuard.validate_model_deployable(
                MetadataStatus(model.status)
            )

            try:
                ver = await resolver.resolve_version(
                    model_id=model.model_id,
                    version_id=version_id,
                    version=version,
                )
            except VersionNotFoundError as exc:
                raise DeploymentError(
                    f"模型{exc}"
                ) from exc

            ModelGuard.validate_version_deployable(
                VersionStatus(ver.status)
            )

            resolved_threshold = (
                None
                if normalized_rollout_type == RolloutType.SHADOW.value
                else self._resolve_threshold(
                    task_type=model.task_type,
                    threshold=threshold,
                )
            )

            deployment = deployment_repo.create_deployment(
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
                framework=Framework(model.framework),
                environment=Environment(environment),
                rollout_type=normalized_rollout_type,
                role=normalized_role,
                threshold=resolved_threshold,
                description=description,
                deployed_by=deployed_by,
            )

            logger.info(
                "创建部署成功",
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }

    @staticmethod
    def validate_release_mode(
            *,
            rollout_type: str,
            role: str,
    ) -> None:
        """校验发布方式和部署角色"""
        try:
            rollout = RolloutType(
                rollout_type
            )
        except ValueError:
            raise DeploymentError(
                "不支持的发布方式: "
                f"{rollout_type or '未提供'}"
            ) from None

        try:
            deployment_role = DeploymentRole(
                role
            )
        except ValueError:
            raise DeploymentError(
                "不支持的部署角色: "
                f"{role or '未提供'}"
            ) from None

        if (
                rollout is RolloutType.SHADOW
                and deployment_role is not DeploymentRole.SHADOW
        ):
            raise DeploymentError(
                "影子发布必须使用 shadow 部署角色"
            )

        if (
                rollout is not RolloutType.SHADOW
                and deployment_role is DeploymentRole.SHADOW
        ):
            raise DeploymentError(
                "shadow 部署角色只能用于影子发布"
            )

        if (
                rollout is RolloutType.FULL
                and deployment_role is not DeploymentRole.CHAMPION
        ):
            raise DeploymentError(
                "全量发布必须使用 champion 部署角色"
            )

    async def enable_deployment(
            self,
            *,
            deployment_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """启用部署并请求 Worker 装载模型

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于启用状态
            InvalidModelStateError: 模型或模型版本状态不允许部署
        """
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=MetadataRepository(uow.session),
                version_repo=VersionRepository(uow.session),
            )

            deployment = await deployment_repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            try:
                model = await resolver.resolve_model(
                    model_id=deployment.model_id
                )
            except ModelNotFoundError as exc:
                raise DeploymentError(
                    str(exc)
                ) from exc

            current_status = DeploymentStatus(deployment.status)
            metadata_status = MetadataStatus(model.status)

            try:
                version = await resolver.resolve_version(
                    model_id=deployment.model_id,
                    version_id=deployment.version_id,
                )
            except VersionNotFoundError as exc:
                raise DeploymentError(
                    f"模型{exc}"
                ) from exc

            ModelGuard.validate_version_deployable(
                VersionStatus(version.status)
            )

            ModelGuard.validate_enable_deployment(
                current=current_status,
                metadata_status=metadata_status,
            )

            deployment_repo.activate_deployment(
                deployment,
                updated_by=updated_by,
            )

            control_repo = ControlRepository(uow.session)
            control = await control_repo.get_deployment_control(
                deployment_id
            )

            if control is None:
                control = control_repo.create_control(
                    control_id=generate_random_id(prefix="ctl"),
                    deployment_id=deployment_id,
                    environment=Environment(
                        deployment.environment
                    ),
                    created_by=updated_by,
                )

            control_repo.set_loaded(
                control,
                updated_by=updated_by,
            )

            logger.info(
                "启用部署成功",
                deployment_id=deployment_id,
                model_id=deployment.model_id,
            )

            result = {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }
            return MutationResult(
                result,
                before={"status": str(current_status)},
                after={"status": str(deployment.status)},
            )

    async def disable_deployment(
            self,
            *,
            deployment_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """禁用部署

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status
                - disabled_routing_ids

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于禁用状态

        说明：
            停用部署会在同一事务中停用其所有已启用路由。
            重新启用部署时不会自动恢复路由。
        """
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=MetadataRepository(uow.session),
                version_repo=VersionRepository(uow.session),
            )

            deployment = await deployment_repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            try:
                await resolver.resolve_model(
                    model_id=deployment.model_id
                )
            except ModelNotFoundError as exc:
                raise DeploymentError(
                    str(exc)
                ) from exc

            current_status = DeploymentStatus(deployment.status)

            ModelGuard.validate_disable_deployment(
                current=current_status,
            )

            experiment_repo = ExperimentRepository(
                uow.session
            )
            running_experiment = (
                await experiment_repo.get_running_experiment(
                    model_id=deployment.model_id,
                    environment=Environment(
                        deployment.environment
                    ),
                )
            )

            if running_experiment is not None:
                variant_repo = VariantRepository(
                    uow.session
                )
                variants = await variant_repo.list_variants(
                    experiment_id=running_experiment.experiment_id,
                    deployment_id=deployment_id,
                    status=ExperimentVariantStatus.ACTIVE,
                    limit=1,
                )

                if variants:
                    raise InvalidDeploymentStateError(
                        "部署正在被运行中的实验引用，不能禁用\n"
                        f"部署 ID: {deployment_id}\n"
                        "实验 ID: "
                        f"{running_experiment.experiment_id}"
                    )

            routing_repo = RoutingRepository(uow.session)
            enabled_routings = await routing_repo.list_routings(
                deployment_id=deployment_id,
                enabled=True,
            )

            for routing in enabled_routings:
                routing_repo.disable_routing(
                    routing,
                    updated_by=updated_by,
                )

            deployment_repo.deactivate_deployment(
                deployment,
                updated_by=updated_by,
            )

            control_repo = ControlRepository(uow.session)
            control = await control_repo.get_deployment_control(
                deployment_id
            )

            if control is None:
                control_repo.create_control(
                    control_id=generate_random_id(prefix="ctl"),
                    deployment_id=deployment_id,
                    environment=Environment(
                        deployment.environment
                    ),
                    created_by=updated_by,
                )
            else:
                control_repo.set_unloaded(
                    control,
                    updated_by=updated_by,
                )

            logger.info(
                "禁用部署成功",
                deployment_id=deployment_id,
                model_id=deployment.model_id,
                disabled_routing_count=len(enabled_routings),
            )

            result = {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
                "disabled_routing_ids": [
                    routing.routing_id
                    for routing in enabled_routings
                ],
            }
            return MutationResult(
                result,
                before={"status": str(current_status)},
                after={"status": str(deployment.status)},
            )

    async def update_deployment(
            self,
            *,
            deployment_id: str,
            environment: str | None = None,
            rollout_type: str | None = None,
            role: str | None = None,
            threshold: float | None = None,
            description: str | None = None,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """更新已停用部署的发布方式、运行配置和说明"""
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)
            deployment = await deployment_repo.get_deployment(deployment_id)

            if deployment is None:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if DeploymentStatus(deployment.status) is not DeploymentStatus.INACTIVE:
                raise InvalidDeploymentStateError(
                    "启用状态的部署无法编辑，请先停用部署"
                )

            resolved_rollout_type = (
                rollout_type.strip().lower()
                if rollout_type is not None
                else deployment.rollout_type
            )
            resolved_role = (
                role.strip().lower()
                if role is not None
                else deployment.role
            )
            self.validate_release_mode(
                rollout_type=resolved_rollout_type,
                role=resolved_role,
            )

            if resolved_rollout_type == RolloutType.SHADOW.value:
                deployment.threshold = None

            resolved_threshold = None
            if threshold is not None:
                model = await MetadataRepository(
                    uow.session
                ).get_model(model_id=deployment.model_id)
                if model is None:
                    raise DeploymentError(
                        f"模型不存在: {deployment.model_id}"
                    )
                resolved_threshold = self._resolve_threshold(
                    task_type=model.task_type,
                    threshold=threshold,
                )

            deployment_repo.update_deployment(
                deployment,
                DeploymentPatch(
                    environment=(
                        Environment(environment)
                        if environment is not None
                        else None
                    ),
                    rollout_type=(
                        resolved_rollout_type
                        if rollout_type is not None
                        else None
                    ),
                    role=(
                        resolved_role
                        if role is not None
                        else None
                    ),
                    threshold=resolved_threshold,
                    description=description,
                ),
                updated_by=updated_by,
            )

            if any(
                    value is not None
                    for value in (
                        environment,
                        rollout_type,
                        role,
                    )
            ):
                routing_repo = RoutingRepository(uow.session)
                routings = await routing_repo.list_routings(
                    deployment_id=deployment_id,
                    include_deleted=True,
                )
                routing_patch = RoutingPatch(
                    environment=(
                        Environment(environment)
                        if environment is not None
                        else Environment(deployment.environment)
                    ),
                    rollout_type=resolved_rollout_type,
                    rollout_group=resolved_role,
                    traffic_ratio=(
                        1.0
                        if resolved_rollout_type == "full"
                        else None
                    ),
                )
                for routing in routings:
                    routing_repo.update_routing(
                        routing,
                        routing_patch,
                        updated_by=updated_by,
                    )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "threshold": deployment.threshold,
                "description": deployment.description,
                "status": deployment.status,
            }

    async def delete_deployment(
            self,
            *,
            deployment_id: str,
            reason: str | None = None,
            deleted_by: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除已停用且已卸载的部署"""
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )
            deployment = await deployment_repo.get_deployment(
                deployment_id
            )

            if deployment is None:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if (
                    DeploymentStatus(
                        deployment.status
                    )
                    is not DeploymentStatus.INACTIVE
            ):
                raise InvalidDeploymentStateError(
                    "启用状态的部署无法删除，"
                    "请先停用部署"
                )

            control = await ControlRepository(
                uow.session
            ).get_deployment_control(
                deployment_id
            )

            if (
                    control is not None
                    and control.desired_status
                    == str(
                        RuntimeControlStatus.LOADED
                    )
            ):
                raise InvalidDeploymentStateError(
                    "部署仍处于加载期望状态，"
                    "请重新启用后再停用部署: "
                    f"{deployment_id}"
                )

            runtime_repo = RuntimeRepository(
                uow.session
            )
            runtimes = await runtime_repo.list_runtimes(
                deployment_id=deployment_id,
            )
            active_runtimes = [
                runtime
                for runtime in runtimes
                if runtime.status in {"starting", "running", "stopping"}
            ]
            unload_requested = (
                control is not None
                and control.desired_status
                == str(RuntimeControlStatus.UNLOADED)
            )
            stale_runtime_ids: list[str] = []

            if unload_requested and active_runtimes:
                heartbeat_deadline = (
                    datetime.now(timezone.utc)
                    - timedelta(
                        seconds=(
                            get_settings().runtime.heartbeat_interval
                            * 3
                        )
                    )
                )
                remaining_active_runtimes = []

                for runtime in active_runtimes:
                    heartbeat_value = runtime.last_heartbeat_at
                    last_heartbeat_at: datetime | None = (
                        heartbeat_value
                        if isinstance(heartbeat_value, datetime)
                        else None
                    )
                    if (
                            last_heartbeat_at is None
                            or last_heartbeat_at >= heartbeat_deadline
                    ):
                        remaining_active_runtimes.append(runtime)
                        continue

                    runtime_repo.mark_stopped(
                        runtime,
                        stopped_by=deleted_by,
                        context={
                            **(getattr(runtime, "context", None) or {}),
                            "reason": "stale_runtime_finalized_on_delete",
                        },
                    )
                    stale_runtime_ids.append(runtime.runtime_id)

                active_runtimes = remaining_active_runtimes

            active_runtime_ids = [
                runtime.runtime_id
                for runtime in active_runtimes
            ]

            if active_runtime_ids:
                raise InvalidDeploymentStateError(
                    "部署仍存在未卸载的运行实例: "
                    + ", ".join(
                        active_runtime_ids
                    )
                )

            routings = await RoutingRepository(
                uow.session
            ).list_enabled_routings(
                deployment_id=deployment_id,
            )

            if routings:
                raise InvalidDeploymentStateError(
                    "部署仍被启用状态的路由引用: "
                    + ", ".join(
                        routing.routing_id
                        for routing in routings
                    )
                )

            variants = await VariantRepository(
                uow.session
            ).list_variants(
                deployment_id=deployment_id,
            )
            blocking_variant_ids: list[str] = []
            terminal_experiment_statuses = {
                ExperimentStatus.STOPPED,
                ExperimentStatus.COMPLETED,
                ExperimentStatus.ARCHIVED,
            }
            experiment_repo = ExperimentRepository(
                uow.session
            )

            for variant in variants:
                if (
                        ExperimentVariantStatus(
                            variant.status
                        )
                        is ExperimentVariantStatus.ARCHIVED
                ):
                    continue

                experiment = await experiment_repo.get_experiment(
                    variant.experiment_id
                )

                if (
                        experiment is not None
                        and ExperimentStatus(
                            experiment.status
                        )
                        not in terminal_experiment_statuses
                ):
                    blocking_variant_ids.append(
                        variant.variant_id
                    )

            if blocking_variant_ids:
                raise InvalidDeploymentStateError(
                    "部署仍被有效实验分组引用: "
                    + ", ".join(
                        blocking_variant_ids
                    )
                )

            deployment_repo.mark_deleted(
                deployment,
                deleted_by=deleted_by,
                deletion_reason=reason,
            )

            logger.info(
                "删除部署成功",
                deployment_id=deployment_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "finalized_runtime_ids": stale_runtime_ids,
                "action": "delete_deployment",
            }

    async def restore_deployment(
            self,
            *,
            deployment_id: str,
            restored_by: str | None = None,
    ) -> dict[str, Any]:
        """恢复逻辑删除的部署，恢复后保持停用"""
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )
            deployment = await deployment_repo.get_deployment(
                deployment_id,
                include_deleted=True,
            )

            if deployment is None:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if deployment.deleted_at is None:
                raise InvalidDeploymentStateError(
                    "部署未被逻辑删除"
                )

            deployment_repo.restore_deployment(
                deployment,
                restored_by=restored_by,
            )

            logger.info(
                "恢复部署成功",
                deployment_id=deployment_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "status": deployment.status,
                "action": "restore_deployment",
            }

    @staticmethod
    def _resolve_threshold(
            *,
            task_type: str,
            threshold: float | None,
    ) -> float:
        """解析并校验决策阈值

        参数：
            task_type: 任务类型
            threshold: 显式决策阈值（可选）

        返回：
            决策阈值

        异常：
            DeploymentError: 不支持的任务类型或配置校验失败
        """
        try:
            if task_type == "classification":
                return ClassificationConfig(
                    threshold=threshold
                    if threshold is not None
                    else ClassificationConfig().threshold
                ).threshold

            if task_type == "scoring":
                return ScoringConfig(
                    threshold=threshold
                    if threshold is not None
                    else ScoringConfig().threshold
                ).threshold

            raise DeploymentError(
                f"不支持的任务类型: {task_type}"
            )

        except DeploymentError:
            raise
        except Exception as exc:
            raise DeploymentError(
                f"配置校验失败: {exc}"
            ) from exc
