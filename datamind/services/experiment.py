"""实验生命周期服务.

负责实验及分组的创建、更新、状态管理、逻辑删除与恢复。

核心功能：
  - create_experiment: 创建实验
  - update_experiment: 更新实验
  - create_variant: 创建实验分组
  - update_variant: 更新实验分组
  - transition_experiment: 迁移实验状态
  - set_variant_active: 设置分组启用状态
  - delete_experiment: 逻辑删除实验
  - restore_experiment: 恢复实验
  - delete_variant: 逻辑删除实验分组
  - restore_variant: 恢复实验分组
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Any

import structlog

from datamind.config import get_logging_config
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    ExperimentPatch,
    ExperimentRepository,
    MetadataRepository,
    VariantPatch,
    VariantRepository,
)
from datamind.models.enums import (
    AssignmentStrategy,
    DeploymentStatus,
    ExperimentStatus,
    ExperimentVariantStatus,
)
from datamind.models.errors import (
    ExperimentError,
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
)
from datamind.services.mutation import MutationResult
from datamind.utils.datetime import (
    format_iso_utc,
    parse_datetime,
    to_utc,
)
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


class _Unset:
    """标记更新请求未提供的字段."""


_UNSET = _Unset()


class ExperimentLifecycleService:
    """实验生命周期服务."""

    async def create_experiment(
            self,
            *,
            model_id: str,
            environment: str,
            name: str,
            strategy: str = AssignmentStrategy.HASH.value,
            traffic_ratio: float = 1.0,
            bucket_key: str = "subject_key",
            groups: list[dict[str, Any]] | None = None,
            manual_assignments: dict[str, str] | None = None,
            description: str | None = None,
            effective_from: str | None = None,
            effective_to: str | None = None,
            created_by: str | None = None,
    ) -> dict[str, Any]:
        """创建草稿实验."""
        resolved_environment = Environment(
            environment
        )
        resolved_strategy = AssignmentStrategy(
            strategy
        )
        timezone_name = get_logging_config().timezone
        start = parse_datetime(
            effective_from,
            timezone_name=timezone_name,
        )
        end = parse_datetime(
            effective_to,
            timezone_name=timezone_name,
        )

        if end is not None and start is not None and end <= start:
            raise InvalidExperimentConfigError(
                "失效时间必须晚于生效时间"
            )

        if resolved_strategy is AssignmentStrategy.HASH and traffic_ratio <= 0:
            raise InvalidExperimentConfigError(
                "hash 策略的实验流量比例必须大于 0"
            )

        async with UnitOfWork() as uow:
            metadata = await MetadataRepository(
                uow.session
            ).get_model(
                model_id=model_id
            )

            if metadata is None:
                raise ExperimentError(
                    f"模型不存在: {model_id}"
                )

            experiment = ExperimentRepository(
                uow.session
            ).create_experiment(
                experiment_id=generate_random_id(
                    prefix="exp"
                ),
                model_id=model_id,
                environment=resolved_environment,
                name=name,
                description=description,
                config={
                    "strategy": str(resolved_strategy),
                    "traffic_ratio": traffic_ratio,
                    "bucket_key": bucket_key,
                },
                effective_from=start,
                effective_to=end,
                created_by=created_by,
            )

            created_groups = []
            if groups is not None:
                created_groups = await self._create_initial_groups(
                    uow,
                    experiment,
                    groups,
                    created_by=created_by,
                )

            if manual_assignments is not None:
                if resolved_strategy is not AssignmentStrategy.MANUAL:
                    raise InvalidExperimentConfigError(
                        "只有手动分配策略支持指定客户"
                    )

                group_ids = {
                    group["key"]: variant.variant_id
                    for group, variant in zip(
                        groups or [],
                        created_groups,
                        strict=True,
                    )
                }

                if any(
                        key not in group_ids
                        for key in manual_assignments.values()
                ):
                    raise InvalidExperimentConfigError(
                        "客户指定的目标分组不存在"
                    )

                assignments = {
                    customer: group_ids[key]
                    for customer, key in manual_assignments.items()
                }
                self._validate_manual_assignments(
                    assignments,
                    created_groups,
                )
                experiment.config = {
                    **experiment.config,
                    "manual_assignments": assignments,
                }

            result = self._experiment_result(experiment)

            if groups is not None:
                result["variants"] = [
                    self._variant_result(item)
                    for item in created_groups
                ]

            return MutationResult(result, after=result)

    async def _create_initial_groups(
            self,
            uow: UnitOfWork,
            experiment: Any,
            groups: list[dict[str, Any]],
            *,
            created_by: str | None,
    ) -> list[Any]:
        """在创建实验的事务内组织初始分组创建."""
        if not groups:
            raise InvalidExperimentConfigError(
                "请至少配置一个分组"
            )

        keys = [
            group["key"]
            for group in groups
        ]

        if any(
                not isinstance(key, str) or not key.strip()
                for key in keys
        ):
            raise InvalidExperimentConfigError(
                "分组标识不能为空"
            )

        if len(set(keys)) != len(keys):
            raise InvalidExperimentConfigError(
                "分组标识不能重复"
            )

        # 显式写入父记录，确保分组外键在同一事务内可用。
        await uow.session.flush()

        variants = []

        for group in groups:
            variant = await self._create_variant(
                uow,
                experiment,
                variants,
                name=group["name"],
                deployment_id=group["deployment_id"],
                weight=group["weight"],
                is_control=group.get("is_control", False),
                created_by=created_by,
            )
            variants.append(variant)

        return variants

    async def update_experiment(
            self,
            *,
            experiment_id: str,
            name: str | None = None,
            strategy: str | None = None,
            traffic_ratio: float | None = None,
            bucket_key: str | None = None,
            manual_assignments: dict[str, str] | None = None,
            description: str | None = None,
            effective_from: str | None = None,
            effective_to: str | None = None,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """更新草稿实验的基本信息和分流配置."""
        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)
            experiment = await repo.get_experiment(experiment_id)
            if experiment is None:
                raise ExperimentError(f"实验不存在: {experiment_id}")
            if ExperimentStatus(experiment.status) is not ExperimentStatus.DRAFT:
                raise InvalidExperimentStateError(
                    "只有草稿状态的实验允许编辑"
                )

            current_config = dict(experiment.config or {})
            if strategy is not None:
                current_config["strategy"] = str(AssignmentStrategy(strategy))
            if traffic_ratio is not None:
                current_config["traffic_ratio"] = traffic_ratio
            if bucket_key is not None:
                current_config["bucket_key"] = bucket_key
            if current_config.get("strategy") == "manual":
                if manual_assignments is not None:
                    variants = await VariantRepository(uow.session).list_active_variants(experiment_id)
                    self._validate_manual_assignments(manual_assignments, variants)
                    current_config["manual_assignments"] = manual_assignments
            else:
                if manual_assignments:
                    raise InvalidExperimentConfigError("只有手动分配策略支持指定客户")
                current_config.pop("manual_assignments", None)

            timezone_name = get_logging_config().timezone
            start = (
                parse_datetime(effective_from, timezone_name=timezone_name)
                if effective_from is not None
                else experiment.effective_from
            )
            end = (
                parse_datetime(effective_to, timezone_name=timezone_name)
                if effective_to is not None
                else experiment.effective_to
            )
            if end is not None and start is not None and end <= start:
                raise InvalidExperimentConfigError(
                    "失效时间必须晚于生效时间"
                )

            before = self._experiment_result(experiment)
            repo.update_experiment(
                experiment,
                ExperimentPatch(
                    name=name,
                    description=description,
                    config=current_config,
                    effective_from=start,
                    effective_to=end,
                ),
                updated_by=updated_by,
            )
            result = self._experiment_result(experiment)
            return MutationResult.changed(
                result, before=before, after=result
            )

    async def create_variant(
            self,
            *,
            experiment_id: str,
            name: str,
            deployment_id: str,
            weight: float,
            is_control: bool = False,
            config: dict[str, Any] | None = None,
            description: str | None = None,
            created_by: str | None = None,
    ) -> dict[str, Any]:
        """为草稿实验创建启用状态的分组."""
        async with UnitOfWork() as uow:
            experiment = await ExperimentRepository(
                uow.session
            ).get_experiment(
                experiment_id
            )

            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {experiment_id}"
                )

            variants = await VariantRepository(
                uow.session
            ).list_variants(
                experiment_id=experiment_id,
            )
            variant = await self._create_variant(
                uow,
                experiment,
                variants,
                name=name,
                deployment_id=deployment_id,
                weight=weight,
                is_control=is_control,
                config=config,
                description=description,
                created_by=created_by,
            )

            result = self._variant_result(variant)
            return MutationResult(result, after=result)

    @staticmethod
    async def _create_variant(
            uow: UnitOfWork,
            experiment: Any,
            variants: list[Any],
            *,
            name: str,
            deployment_id: str,
            weight: float,
            is_control: bool = False,
            config: dict[str, Any] | None = None,
            description: str | None = None,
            created_by: str | None = None,
    ) -> Any:
        """复用当前事务校验并创建分组."""
        variant_repo = VariantRepository(
            uow.session
        )
        deployment_repo = DeploymentRepository(
            uow.session
        )

        if not isinstance(name, str) or not name.strip():
            raise InvalidExperimentConfigError(
                "分组名称不能为空"
            )

        if not 0 < weight <= 1:
            raise InvalidExperimentConfigError(
                "分组权重必须大于 0 且不超过 1"
            )

        if ExperimentStatus(experiment.status) is not ExperimentStatus.DRAFT:
            raise InvalidExperimentStateError(
                "只有草稿状态的实验允许添加分组"
            )

        deployment = await deployment_repo.get_deployment(
            deployment_id
        )

        if deployment is None:
            raise InvalidExperimentConfigError(
                f"部署不存在: {deployment_id}"
            )

        if deployment.model_id != experiment.model_id:
            raise InvalidExperimentConfigError(
                "部署所属模型与实验模型不一致"
            )

        if deployment.environment != experiment.environment:
            raise InvalidExperimentConfigError(
                "部署环境与实验环境不一致"
            )

        if DeploymentStatus(deployment.status) is not DeploymentStatus.ACTIVE:
            raise InvalidExperimentConfigError(
                "分组只能绑定启用状态的部署"
            )

        if (
                str(deployment.rollout_type).lower() == "shadow"
                or str(deployment.role).lower() == "shadow"
        ):
            raise InvalidExperimentConfigError(
                "影子部署不能绑定实验分组"
            )

        for current in variants:
            if current.name == name:
                raise InvalidExperimentConfigError(
                    f"实验已存在同名分组: {current.variant_id}"
                )

            if current.deployment_id == deployment_id:
                raise InvalidExperimentConfigError(
                    "实验已存在绑定该部署的分组: "
                    f"{current.variant_id}"
                )

            if is_control and current.is_control and (
                    ExperimentVariantStatus(current.status)
                    is ExperimentVariantStatus.ACTIVE
            ):
                raise InvalidExperimentConfigError(
                    "实验已存在启用状态的对照组"
                )

        strategy = AssignmentStrategy(
            str((experiment.config or {}).get(
                "strategy",
                AssignmentStrategy.HASH,
            ))
        )

        if strategy is AssignmentStrategy.HASH:
            active_weight = sum(
                float(item.weight or 0)
                for item in variants
                if ExperimentVariantStatus(item.status)
                is ExperimentVariantStatus.ACTIVE
            )

            if active_weight + weight > 1.0 + 1e-8:
                raise InvalidExperimentConfigError(
                    "启用状态分组的权重之和不能大于 1"
                )

        variant = variant_repo.create_variant(
            variant_id=generate_random_id(
                prefix="var"
            ),
            experiment_id=experiment.experiment_id,
            name=name,
            deployment_id=deployment_id,
            weight=weight,
            is_control=is_control,
            config=config or {
                "group": "control" if is_control else "treatment",
                "environment": experiment.environment,
            },
            description=description,
            created_by=created_by,
        )

        return variant

    async def update_variant(
            self,
            *,
            variant_id: str,
            name: str | None = None,
            weight: float | None = None,
            is_control: bool | None = None,
            config: dict[str, Any] | None | _Unset = _UNSET,
            description: str | None = None,
            updated_by: str | None = None,
    ) -> MutationResult:
        """更新草稿实验中的分组配置.

        未提供的配置保持不变，显式传入 None 则清空。
        """
        async with UnitOfWork() as uow:
            variant_repo = VariantRepository(uow.session)
            experiment_repo = ExperimentRepository(uow.session)
            variant = await variant_repo.get_variant(variant_id)
            if variant is None:
                raise ExperimentError(f"实验分组不存在: {variant_id}")

            experiment = await experiment_repo.get_experiment(
                variant.experiment_id
            )
            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {variant.experiment_id}"
                )
            if ExperimentStatus(experiment.status) is not ExperimentStatus.DRAFT:
                raise InvalidExperimentStateError(
                    "只有草稿状态实验中的分组允许编辑"
                )

            variants = await variant_repo.list_variants(
                experiment_id=variant.experiment_id,
            )
            for current in variants:
                if current.variant_id == variant_id:
                    continue
                if name is not None and current.name == name:
                    raise InvalidExperimentConfigError(
                        f"实验已存在同名分组: {current.variant_id}"
                    )
                if (
                        is_control is True
                        and current.is_control
                        and ExperimentVariantStatus(current.status)
                        is ExperimentVariantStatus.ACTIVE
                ):
                    raise InvalidExperimentConfigError(
                        "实验只能有一个启用状态的对照组"
                    )

            if (
                    weight is not None
                    and ExperimentVariantStatus(variant.status)
                    is ExperimentVariantStatus.ACTIVE
            ):
                active_total = sum(
                    float(current.weight)
                    for current in variants
                    if current.variant_id != variant_id
                    and ExperimentVariantStatus(current.status)
                    is ExperimentVariantStatus.ACTIVE
                )
                if active_total + weight > 1.0 + 1e-9:
                    raise InvalidExperimentConfigError(
                        "启用分组的权重总和不能超过 1"
                    )

            before = self._variant_result(variant)
            variant_repo.update_variant(
                variant,
                VariantPatch(
                    name=name,
                    weight=weight,
                    is_control=is_control,
                    description=description,
                ),
                updated_by=updated_by,
            )
            if not isinstance(config, _Unset):
                variant.config = config
            result = self._variant_result(variant)
            return MutationResult.changed(
                result, before=before, after=result
            )

    async def transition_experiment(
            self,
            *,
            experiment_id: str,
            action: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """执行实验启动、暂停、停止、完成或归档操作."""
        operations = {
            "start": "start_experiment",
            "pause": "pause_experiment",
            "stop": "stop_experiment",
            "complete": "complete_experiment",
            "archive": "archive_experiment",
        }

        if action not in operations:
            raise ValueError(
                f"不支持的实验操作: {action}"
            )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(
                uow.session
            )
            variant_repo = VariantRepository(
                uow.session
            )
            deployment_repo = DeploymentRepository(
                uow.session
            )
            experiment = await experiment_repo.get_experiment(
                experiment_id
            )

            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {experiment_id}"
                )

            if action == "start":
                running_experiment = (
                    await experiment_repo.get_running_experiment(
                        model_id=experiment.model_id,
                        environment=Environment(
                            experiment.environment
                        ),
                        exclude_experiment_id=experiment.experiment_id,
                    )
                )

                if running_experiment is not None:
                    raise InvalidExperimentConfigError(
                        "模型在当前环境下已存在运行中的实验: "
                        f"{running_experiment.experiment_id}"
                    )

                variants = await variant_repo.list_active_variants(
                    experiment_id
                )

                if not variants:
                    raise InvalidExperimentConfigError(
                        "实验没有可用的启用状态分组，请先添加实验分组"
                    )

                if (experiment.config or {}).get("strategy") == "manual":
                    assignments = (experiment.config or {}).get(
                        "manual_assignments"
                    )

                    if not assignments:
                        raise InvalidExperimentConfigError(
                            "请先编辑实验并指定客户及目标分组"
                        )

                    if not isinstance(assignments, dict):
                        raise InvalidExperimentConfigError(
                            "手动分配配置必须为客户标识到分组 ID 的映射"
                        )

                    self._validate_manual_assignments(
                        assignments,
                        variants,
                    )

                await self._validate_variant_deployments(
                    deployment_repo=deployment_repo,
                    experiment=experiment,
                    variants=variants,
                    now=datetime.now(
                        timezone.utc
                    ),
                )

                if sum(bool(item.is_control) for item in variants) != 1:
                    raise InvalidExperimentConfigError(
                        "实验必须且只能包含一个启用状态的对照组"
                    )

                if not any(not item.is_control for item in variants):
                    raise InvalidExperimentConfigError(
                        "实验至少需要包含一个启用状态的实验组"
                    )

                strategy = AssignmentStrategy(
                    str((experiment.config or {}).get(
                        "strategy",
                        AssignmentStrategy.HASH,
                    ))
                )

                if strategy is AssignmentStrategy.HASH and abs(
                        sum(float(item.weight) for item in variants) - 1.0
                ) > 0.000001:
                    raise InvalidExperimentConfigError(
                        "hash 策略下启用状态分组的权重之和必须等于 1"
                    )

            before = self._experiment_result(experiment)
            operation = getattr(
                experiment_repo,
                operations[action],
            )
            operation(
                experiment,
                updated_by=updated_by,
            )

            result = self._experiment_result(experiment)
            return MutationResult.changed(
                result, before=before, after=result
            )

    @staticmethod
    def _validate_manual_assignments(
            assignments: dict[str, str],
            variants: list[Any],
    ) -> None:
        """校验客户标识及其所属实验的启用分组."""
        targets = {
            variant.variant_id
            for variant in variants
        }

        for subject, target in assignments.items():
            if (
                    not isinstance(subject, str)
                    or not subject.strip()
                    or subject != subject.strip()
                    or len(subject) > 128
            ):
                raise InvalidExperimentConfigError(
                    "客户标识不能为空、超过 128 个字符或包含首尾空格"
                )

            if (
                    not isinstance(target, str)
                    or target not in targets
            ):
                raise InvalidExperimentConfigError(
                    f"客户 {subject} 的目标分组不存在或未启用"
                )

    @staticmethod
    async def _validate_variant_deployments(
            *,
            deployment_repo: DeploymentRepository,
            experiment: Any,
            variants: list[Any],
            now: datetime,
    ) -> None:
        """校验启用状态分组绑定的部署可参与实验."""
        deployment_variants: dict[str, str] = {}

        for variant in variants:
            existing_variant_id = deployment_variants.get(
                variant.deployment_id
            )

            if existing_variant_id is not None:
                raise InvalidExperimentConfigError(
                    "启用状态实验分组必须绑定不同部署: "
                    f"{existing_variant_id}, {variant.variant_id}"
                )

            deployment_variants[
                variant.deployment_id
            ] = variant.variant_id

        for variant in variants:
            deployment = await deployment_repo.get_deployment(
                variant.deployment_id
            )

            if deployment is None:
                raise InvalidExperimentConfigError(
                    "实验分组绑定的部署不存在: "
                    f"{variant.deployment_id}"
                )

            if deployment.model_id != experiment.model_id:
                raise InvalidExperimentConfigError(
                    "实验分组绑定的部署所属模型与实验模型不一致: "
                    f"{variant.variant_id}"
                )

            if deployment.environment != experiment.environment:
                raise InvalidExperimentConfigError(
                    "实验分组绑定的部署环境与实验环境不一致: "
                    f"{variant.variant_id}"
                )

            if (
                    str(deployment.rollout_type).lower() == "shadow"
                    or str(deployment.role).lower() == "shadow"
            ):
                raise InvalidExperimentConfigError(
                    "实验分组不能使用影子部署: "
                    f"{deployment.deployment_id}"
                )

            if deployment.status != str(
                    DeploymentStatus.ACTIVE
            ):
                raise InvalidExperimentConfigError(
                    "实验分组绑定的部署未启用: "
                    f"{deployment.deployment_id}"
                )

            current_time = to_utc(
                now
            )
            effective_from = deployment.effective_from
            effective_to = deployment.effective_to

            if (
                    effective_from is not None
                    and to_utc(effective_from) > current_time
            ) or (
                    effective_to is not None
                    and to_utc(effective_to) <= current_time
            ):
                raise InvalidExperimentConfigError(
                    "实验分组绑定的部署不在生效时间内: "
                    f"{deployment.deployment_id}"
                )

    async def set_variant_active(
            self,
            *,
            variant_id: str,
            active: bool,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """设置实验分组启用状态."""
        async with UnitOfWork() as uow:
            repo = VariantRepository(
                uow.session
            )
            variant = await repo.get_variant(
                variant_id
            )

            if variant is None:
                raise ExperimentError(
                    f"实验分组不存在: {variant_id}"
                )

            before = self._variant_result(variant)
            if active:
                repo.activate_variant(
                    variant,
                    updated_by=updated_by,
                )
            else:
                repo.deactivate_variant(
                    variant,
                    updated_by=updated_by,
                )

            result = self._variant_result(variant)
            return MutationResult.changed(
                result, before=before, after=result
            )

    @staticmethod
    def _experiment_result(
            experiment: Any,
    ) -> dict[str, Any]:
        """转换实验结果."""
        return {
            "experiment_id": experiment.experiment_id,
            "model_id": experiment.model_id,
            "environment": experiment.environment,
            "name": experiment.name,
            "status": experiment.status,
            "config": experiment.config,
            "effective_from": format_iso_utc(experiment.effective_from),
            "effective_to": format_iso_utc(experiment.effective_to),
        }

    @staticmethod
    def _variant_result(
            variant: Any,
    ) -> dict[str, Any]:
        """转换实验分组结果."""
        return {
            "variant_id": variant.variant_id,
            "experiment_id": variant.experiment_id,
            "name": variant.name,
            "deployment_id": variant.deployment_id,
            "weight": variant.weight,
            "is_control": variant.is_control,
            "status": variant.status,
            "config": variant.config,
        }

    async def delete_experiment(
            self,
            *,
            experiment_id: str,
            reason: str | None = None,
            deleted_by: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除草稿或已归档实验及其分组."""
        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(
                uow.session
            )
            variant_repo = VariantRepository(
                uow.session
            )
            experiment = await experiment_repo.get_experiment(
                experiment_id
            )

            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {experiment_id}"
                )

            status = ExperimentStatus(
                experiment.status
            )

            if status not in {
                ExperimentStatus.DRAFT,
                ExperimentStatus.ARCHIVED,
            }:
                raise InvalidExperimentStateError(
                    "当前状态的实验无法删除，"
                    "请先完成实验生命周期并归档"
                )

            deletion_id = generate_random_id(
                prefix="del"
            )
            deleted_at = datetime.now(
                timezone.utc
            )
            variants = await variant_repo.list_variants(
                experiment_id=experiment_id,
            )

            for variant in variants:
                variant_repo.mark_deleted(
                    variant,
                    deletion_id=deletion_id,
                    deleted_at=deleted_at,
                    deleted_by=deleted_by,
                    deletion_reason=reason,
                )

            experiment_repo.mark_deleted(
                experiment,
                deletion_id=deletion_id,
                deleted_at=deleted_at,
                deleted_by=deleted_by,
                deletion_reason=reason,
            )

            logger.info(
                "删除实验成功",
                experiment_id=experiment_id,
                variant_count=len(
                    variants
                ),
            )

            return {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
                "deletion_id": deletion_id,
                "variant_count": len(
                    variants
                ),
                "action": "delete_experiment",
            }

    async def restore_experiment(
            self,
            *,
            experiment_id: str,
            restored_by: str | None = None,
    ) -> dict[str, Any]:
        """恢复逻辑删除的实验及同批分组."""
        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(
                uow.session
            )
            variant_repo = VariantRepository(
                uow.session
            )
            experiment = await experiment_repo.get_experiment(
                experiment_id,
                include_deleted=True,
            )

            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {experiment_id}"
                )

            if experiment.deleted_at is None:
                raise InvalidExperimentStateError(
                    "实验未被逻辑删除"
                )

            deletion_id = experiment.deletion_id
            variants = await variant_repo.list_variants(
                experiment_id=experiment_id,
                include_deleted=True,
            )
            restored_variants = [
                variant
                for variant in variants
                if variant.deleted_at is not None
                and variant.deletion_id == deletion_id
            ]

            for variant in restored_variants:
                variant_repo.restore_variant(
                    variant,
                    restored_by=restored_by,
                )

            experiment_repo.restore_experiment(
                experiment,
                restored_by=restored_by,
            )

            logger.info(
                "恢复实验成功",
                experiment_id=experiment_id,
            )

            return {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
                "status": experiment.status,
                "variant_count": len(
                    restored_variants
                ),
                "action": "restore_experiment",
            }

    async def delete_variant(
            self,
            *,
            variant_id: str,
            reason: str | None = None,
            deleted_by: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除草稿实验中的分组."""
        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(
                uow.session
            )
            variant_repo = VariantRepository(
                uow.session
            )
            variant = await variant_repo.get_variant(
                variant_id
            )

            if variant is None:
                raise ExperimentError(
                    f"实验分组不存在: {variant_id}"
                )

            experiment = await experiment_repo.get_experiment(
                variant.experiment_id
            )

            if experiment is None:
                raise ExperimentError(
                    f"实验不存在: {variant.experiment_id}"
                )

            if (
                    ExperimentStatus(
                        experiment.status
                    )
                    is not ExperimentStatus.DRAFT
            ):
                raise InvalidExperimentStateError(
                    "实验启动后不能删除分组，"
                    "请停用或归档分组"
                )

            deletion_id = generate_random_id(
                prefix="del"
            )
            variant_repo.mark_deleted(
                variant,
                deletion_id=deletion_id,
                deleted_by=deleted_by,
                deletion_reason=reason,
            )

            logger.info(
                "删除实验分组成功",
                variant_id=variant_id,
            )

            return {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "name": variant.name,
                "deletion_id": deletion_id,
                "action": "delete_variant",
            }

    async def restore_variant(
            self,
            *,
            variant_id: str,
            restored_by: str | None = None,
    ) -> dict[str, Any]:
        """恢复逻辑删除的实验分组."""
        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(
                uow.session
            )
            variant_repo = VariantRepository(
                uow.session
            )
            variant = await variant_repo.get_variant(
                variant_id,
                include_deleted=True,
            )

            if variant is None:
                raise ExperimentError(
                    f"实验分组不存在: {variant_id}"
                )

            if variant.deleted_at is None:
                raise InvalidExperimentStateError(
                    "实验分组未被逻辑删除"
                )

            experiment = await experiment_repo.get_experiment(
                variant.experiment_id
            )

            if experiment is None:
                raise InvalidExperimentStateError(
                    "所属实验不存在或已删除，"
                    "请先恢复实验"
                )

            if (
                    ExperimentStatus(
                        experiment.status
                    )
                    is not ExperimentStatus.DRAFT
            ):
                raise InvalidExperimentStateError(
                    "只能在草稿实验中恢复分组"
                )

            conflicts = await variant_repo.list_variants(
                experiment_id=variant.experiment_id,
            )

            for current in conflicts:
                if current.name == variant.name:
                    raise InvalidExperimentStateError(
                        "实验已存在同名分组: "
                        f"{current.variant_id}"
                    )

                if current.deployment_id == variant.deployment_id:
                    raise InvalidExperimentStateError(
                        "实验已存在绑定该部署的分组: "
                        f"{current.variant_id}"
                    )

            variant_repo.restore_variant(
                variant,
                restored_by=restored_by,
            )

            logger.info(
                "恢复实验分组成功",
                variant_id=variant_id,
            )

            return {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "name": variant.name,
                "status": variant.status,
                "action": "restore_variant",
            }
