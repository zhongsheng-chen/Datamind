"""路由生命周期服务.

负责路由规则的创建、状态管理、逻辑删除与恢复。

核心功能：
  - create_routing: 创建路由规则
  - enable_routing: 启用路由规则
  - disable_routing: 禁用路由规则
  - delete_routing: 逻辑删除路由规则
  - restore_routing: 恢复路由规则
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from datamind.config import get_logging_config
from datamind.db.core import UnitOfWork
from datamind.constants import Environment
from datamind.db.models.deployments import Deployment
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingPatch,
    RoutingRepository,
)
from datamind.models.enums import DeploymentStatus
from datamind.runtime.routing.matcher import RuleMatcher
from datamind.services.mutation import MutationResult
from datamind.utils.datetime import (
    format_iso_utc,
    parse_datetime,
)
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)

_ALLOCATION_EPSILON = 1e-8


class _Unset:
    """标记更新请求未提供的字段."""


_UNSET = _Unset()


def _parse_effective_window(
        *,
        effective_from: str | None,
        effective_to: str | None,
) -> tuple[datetime | None, datetime | None]:
    """解析并校验路由生效区间."""
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
        raise ValueError("失效时间必须晚于生效时间")

    return start, end


def _is_shadow_deployment(deployment: Deployment) -> bool:
    """判断部署是否为不占用主流量预算的影子部署."""
    return (
        str(deployment.rollout_type).lower() == "shadow"
        or str(deployment.role).lower() == "shadow"
    )


def validate_deployment_traffic_ratio(
        *,
        deployment: Deployment,
        traffic_ratio: float,
) -> None:
    """校验部署发布类型对应的路由流量比例."""
    if (
            str(deployment.rollout_type).lower() == "full"
            and abs(float(traffic_ratio) - 1.0) > _ALLOCATION_EPSILON
    ):
        raise ValueError(
            "全量发布的流量比例必须为 100%"
        )


async def validate_routing_allocation(
        *,
        routing_repo: RoutingRepository,
        deployment_repo: DeploymentRepository,
        deployment: Deployment,
        traffic_ratio: float,
        exclude_routing_id: str | None = None,
) -> None:
    """校验启用路由不会超过模型的主流量预算."""
    if str(deployment.status).lower() != DeploymentStatus.ACTIVE.value:
        raise ValueError("只有已启用部署才能启用路由")

    validate_deployment_traffic_ratio(
        deployment=deployment,
        traffic_ratio=traffic_ratio,
    )

    if _is_shadow_deployment(deployment):
        return

    total_ratio = float(traffic_ratio)
    routings = await routing_repo.list_enabled_routings(
        environment=Environment(deployment.environment),
    )

    for routing in routings:
        if routing.routing_id == exclude_routing_id:
            continue

        routed_deployment = await deployment_repo.get_deployment(
            routing.deployment_id
        )

        if (
                routed_deployment is None
                or routed_deployment.model_id != deployment.model_id
                or _is_shadow_deployment(routed_deployment)
        ):
            continue

        total_ratio += float(routing.traffic_ratio)

    if total_ratio > 1.0 + _ALLOCATION_EPSILON:
        raise ValueError(
            "启用后该模型的主路由流量比例将达到 "
            f"{total_ratio:.2%}，不能超过 100.00%"
        )


async def ensure_deployment_has_no_routing(
        *,
        routing_repo: RoutingRepository,
        deployment_id: str,
) -> None:
    """确保一个部署只维护一条未删除路由."""
    existing = await routing_repo.list_routings(
        deployment_id=deployment_id,
        limit=1,
    )

    if existing:
        raise ValueError(
            "该部署已存在路由: "
            f"{existing[0].routing_id}，请编辑现有路由"
        )


class RoutingLifecycleService:
    """路由生命周期服务."""

    async def create_routing(
            self,
            *,
            name: str,
            deployment_id: str,
            environment: str,
            traffic_ratio: float = 1.0,
            enabled: bool = False,
            rules: dict[str, Any] | None = None,
            rules_metadata: dict[str, Any] | None = None,
            effective_from: str | None = None,
            effective_to: str | None = None,
            description: str | None = None,
            created_by: str | None = None,
    ) -> dict[str, Any]:
        """为部署创建路由规则."""
        resolved_name = name.strip()
        if not resolved_name:
            raise ValueError("路由名称不能为空")
        if len(resolved_name) > 128:
            raise ValueError("路由名称不能超过 128 个字符")
        resolved_environment = Environment(
            environment
        )
        start, end = _parse_effective_window(
            effective_from=effective_from,
            effective_to=effective_to,
        )

        if rules is not None:
            RuleMatcher().validate(
                rules
            )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )
            routing_repo = RoutingRepository(
                uow.session
            )
            deployment = await deployment_repo.get_deployment(
                deployment_id
            )

            if deployment is None:
                raise ValueError(
                    f"部署不存在: {deployment_id}"
                )

            if deployment.environment != resolved_environment.value:
                raise ValueError(
                    "路由环境与部署环境不一致"
                )

            validate_deployment_traffic_ratio(
                deployment=deployment,
                traffic_ratio=traffic_ratio,
            )

            await ensure_deployment_has_no_routing(
                routing_repo=routing_repo,
                deployment_id=deployment_id,
            )

            if enabled:
                await validate_routing_allocation(
                    routing_repo=routing_repo,
                    deployment_repo=deployment_repo,
                    deployment=deployment,
                    traffic_ratio=traffic_ratio,
                )

            routing = routing_repo.create_routing(
                routing_id=generate_random_id(
                    prefix="rtn"
                ),
                name=resolved_name,
                deployment_id=deployment_id,
                environment=resolved_environment,
                rollout_type=deployment.rollout_type,
                rollout_group=deployment.role,
                traffic_ratio=traffic_ratio,
                enabled=enabled,
                rules=rules,
                effective_from=start,
                effective_to=end,
                description=description,
                created_by=created_by,
            )

            routing.rules_metadata = self._make_rules_metadata(rules, rules_metadata)
            result = self._routing_result(routing)
            return MutationResult(
                result,
                after=result,
            )

    async def enable_routing(
            self,
            *,
            routing_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """启用路由规则."""
        return await self._set_enabled(
            routing_id=routing_id,
            enabled=True,
            updated_by=updated_by,
        )

    async def update_routing(
            self,
            *,
            routing_id: str,
            name: str | None = None,
            traffic_ratio: float | None = None,
            rules: dict[str, Any] | None | _Unset = _UNSET,
            rules_metadata: dict[str, Any] | None = None,
            effective_from: str | None | _Unset = _UNSET,
            effective_to: str | None | _Unset = _UNSET,
            description: str | None = None,
            updated_by: str | None = None,
    ) -> MutationResult:
        """更新路由基本信息、流量、匹配规则和说明.

        未提供的规则和生效时间保持不变，显式传入 None 则清空。
        """
        resolved_name = None
        if rules_metadata is not None and isinstance(rules, _Unset):
            raise ValueError("上传规则文件时必须同时提供规则内容")
        if name is not None:
            resolved_name = name.strip()
            if not resolved_name:
                raise ValueError("路由名称不能为空")
            if len(resolved_name) > 128:
                raise ValueError("路由名称不能超过 128 个字符")
        if not isinstance(rules, _Unset) and rules is not None:
            RuleMatcher().validate(rules)

        async with UnitOfWork() as uow:
            repo = RoutingRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            routing = await repo.get_routing(routing_id)
            if routing is None:
                raise ValueError(f"路由不存在: {routing_id}")
            before = self._routing_result(routing)

            deployment = await deployment_repo.get_deployment(
                routing.deployment_id
            )
            if deployment is None:
                raise ValueError(
                    f"关联部署不存在: {routing.deployment_id}"
                )

            start = getattr(routing, "effective_from", None)
            end = getattr(routing, "effective_to", None)
            if not isinstance(effective_from, _Unset):
                start = parse_datetime(
                    effective_from,
                    timezone_name=get_logging_config().timezone,
                )
            if not isinstance(effective_to, _Unset):
                end = parse_datetime(
                    effective_to,
                    timezone_name=get_logging_config().timezone,
                )
            if end is not None and start is not None and end <= start:
                raise ValueError("失效时间必须晚于生效时间")

            if traffic_ratio is not None:
                validate_deployment_traffic_ratio(
                    deployment=deployment,
                    traffic_ratio=traffic_ratio,
                )
                if routing.enabled:
                    await validate_routing_allocation(
                        routing_repo=repo,
                        deployment_repo=deployment_repo,
                        deployment=deployment,
                        traffic_ratio=traffic_ratio,
                        exclude_routing_id=routing.routing_id,
                    )

            repo.update_routing(
                routing,
                RoutingPatch(
                    name=resolved_name,
                    traffic_ratio=traffic_ratio,
                    description=description,
                ),
                updated_by=updated_by,
            )
            if not isinstance(rules, _Unset):
                routing.rules = rules
                routing.rules_metadata = self._make_rules_metadata(rules, rules_metadata)
            if not isinstance(effective_from, _Unset):
                routing.effective_from = start
            if not isinstance(effective_to, _Unset):
                routing.effective_to = end
            result = self._routing_result(routing)
            return MutationResult.changed(
                result,
                before=before,
                after=result,
            )

    async def disable_routing(
            self,
            *,
            routing_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """禁用路由规则."""
        return await self._set_enabled(
            routing_id=routing_id,
            enabled=False,
            updated_by=updated_by,
        )

    async def _set_enabled(
            self,
            *,
            routing_id: str,
            enabled: bool,
            updated_by: str | None,
    ) -> dict[str, Any]:
        """设置路由启用状态."""
        async with UnitOfWork() as uow:
            repo = RoutingRepository(
                uow.session
            )
            deployment_repo = DeploymentRepository(uow.session)
            routing = await repo.get_routing(
                routing_id
            )

            if routing is None:
                raise ValueError(
                    f"路由不存在: {routing_id}"
                )

            previous_enabled = bool(routing.enabled)

            if enabled:
                deployment = await deployment_repo.get_deployment(
                    routing.deployment_id
                )
                if deployment is None:
                    raise ValueError(
                        "关联部署不存在: "
                        f"{routing.deployment_id}"
                    )
                await validate_routing_allocation(
                    routing_repo=repo,
                    deployment_repo=deployment_repo,
                    deployment=deployment,
                    traffic_ratio=routing.traffic_ratio,
                    exclude_routing_id=routing.routing_id,
                )
                repo.enable_routing(
                    routing,
                    updated_by=updated_by,
                )
            else:
                repo.disable_routing(
                    routing,
                    updated_by=updated_by,
                )

            return MutationResult(
                self._routing_result(routing),
                before={
                    "enabled": previous_enabled,
                },
                after={
                    "enabled": bool(routing.enabled),
                },
            )

    @staticmethod
    def _make_rules_metadata(
            rules: dict[str, Any] | None,
            file: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """记录本次保存的文件信息，不推断既有规则的上传时间."""
        if rules is None or file is None:
            return None
        return {
            "name": file["name"],
            "size": file["size"],
            "uploaded_at": format_iso_utc(datetime.now(timezone.utc)),
        }

    @staticmethod
    def _routing_result(
            routing: Any,
    ) -> dict[str, Any]:
        """转换路由结果."""
        return {
            "routing_id": routing.routing_id,
            "name": routing.name,
            "deployment_id": routing.deployment_id,
            "environment": routing.environment,
            "rollout_type": routing.rollout_type,
            "rollout_group": routing.rollout_group,
            "traffic_ratio": routing.traffic_ratio,
            "enabled": routing.enabled,
            "rules": routing.rules,
            "rules_metadata": getattr(routing, "rules_metadata", None),
            "effective_from": format_iso_utc(
                getattr(routing, "effective_from", None)
            ),
            "effective_to": format_iso_utc(
                getattr(routing, "effective_to", None)
            ),
            "description": routing.description,
        }

    async def delete_routing(
            self,
            *,
            routing_id: str,
            reason: str | None = None,
            deleted_by: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除已禁用的路由规则."""
        async with UnitOfWork() as uow:
            repo = RoutingRepository(
                uow.session
            )
            routing = await repo.get_routing(
                routing_id
            )

            if routing is None:
                raise ValueError(
                    f"路由不存在: {routing_id}"
                )

            if routing.enabled:
                raise ValueError(
                    "启用状态的路由无法删除，"
                    "请先禁用路由"
                )

            repo.mark_deleted(
                routing,
                deleted_by=deleted_by,
                deletion_reason=reason,
            )

            logger.info(
                "删除路由成功",
                routing_id=routing_id,
            )

            result = {
                "routing_id": routing.routing_id,
                "deployment_id": routing.deployment_id,
                "action": "delete_routing",
            }
            return MutationResult(
                result,
                before={"deleted": False},
                after={"deleted": True},
            )

    async def restore_routing(
            self,
            *,
            routing_id: str,
            restored_by: str | None = None,
    ) -> dict[str, Any]:
        """恢复逻辑删除的路由，恢复后保持禁用."""
        async with UnitOfWork() as uow:
            repo = RoutingRepository(
                uow.session
            )
            routing = await repo.get_routing(
                routing_id,
                include_deleted=True,
            )

            if routing is None:
                raise ValueError(
                    f"路由不存在: {routing_id}"
                )

            if routing.deleted_at is None:
                raise ValueError(
                    "路由未被逻辑删除"
                )

            replacement = await repo.list_routings(
                deployment_id=routing.deployment_id,
                limit=1,
            )
            if replacement:
                raise ValueError(
                    "该部署已存在替代路由: "
                    f"{replacement[0].routing_id}，无法恢复"
                )

            repo.restore_routing(
                routing,
                restored_by=restored_by,
            )

            logger.info(
                "恢复路由成功",
                routing_id=routing_id,
            )

            result = {
                "routing_id": routing.routing_id,
                "deployment_id": routing.deployment_id,
                "enabled": routing.enabled,
                "action": "restore_routing",
            }
            return MutationResult(
                result,
                before={"deleted": True},
                after={"deleted": False},
            )
