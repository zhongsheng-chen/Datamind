# datamind/runtime/routing/router.py

"""运行时路由器

根据请求上下文选择最终命中的部署 ID。

核心功能：
  - resolve: 解析主部署和影子部署路由计划

说明：
  路由按以下优先级解析：
    - 请求指定 deployment_id 时，校验并直接使用该部署。
    - 匹配运行中的实验，并根据 strategy 执行 manual 或 hash 分配。
    - 匹配当前启用且满足请求条件的路由规则。
    - 回退到默认活跃部署，优先选择主部署，其次选择第一个活跃部署。

  如果没有可用部署，则抛出 RuntimeRouteError。

使用示例：
  from datamind.runtime.routing import RuntimeRouter

  router = RuntimeRouter()

  plan = await router.resolve(
      model_id="mdl_0123456789abcdef",
      environment="production",
      subject_key="customer_10001",
      subject_type="customer",
      payload={
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      }
  )

  print(plan.primary.deployment_id)
"""

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from datamind.ab_test.engine import ABTestEngine, ABTestResult
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.models.deployments import Deployment
from datamind.db.models.routing import Routing
from datamind.db.repositories import (
    AssignmentRepository,
    DeploymentRepository,
    ExperimentRepository,
    RoutingRepository,
    VariantRepository,
)
from datamind.models.enums import (
    DecisionStrategy,
    DeploymentRole,
    DeploymentStatus,
    RolloutType,
)
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.routing.matcher import RuleMatcher
from datamind.runtime.routing.policy import validate_traffic_allocation
from datamind.utils.datetime import to_utc

logger = structlog.get_logger(__name__)

@dataclass(slots=True)
class RouteResult:
    """路由结果

    属性：
        model_id: 模型 ID
        version_id: 版本 ID
        deployment_id: 部署 ID
        framework: 框架类型
        environment: 部署环境
        source: 路由来源，可选值 experiment / routing / deployment / shadow / manual
        strategy: 路由策略，可选值 manual / hash / weighted / fallback
        experiment_id: 实验 ID
        variant_id: 实验分组 ID
        assignment_id: 实验分配 ID
        routing_id: 路由 ID
        subject_key: 分桶主体标识
        subject_type: 分桶主体类型
        bucket: 分桶标识
        group: 实验分组名称
        weight: 命中权重
        context: 路由上下文
    """

    model_id: str
    version_id: str
    deployment_id: str
    framework: str
    environment: str

    source: str
    strategy: str

    experiment_id: str | None = None
    variant_id: str | None = None
    assignment_id: str | None = None
    routing_id: str | None = None

    subject_key: str | None = None
    subject_type: str | None = None
    bucket: str | None = None
    group: str | None = None
    weight: float | None = None

    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "model_id": self.model_id,
            "version_id": self.version_id,
            "deployment_id": self.deployment_id,
            "framework": self.framework,
            "environment": self.environment,
            "source": self.source,
            "strategy": self.strategy,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "assignment_id": self.assignment_id,
            "routing_id": self.routing_id,
            "subject_key": self.subject_key,
            "subject_type": self.subject_type,
            "bucket": self.bucket,
            "group": self.group,
            "weight": self.weight,
            "context": self.context,
        }


@dataclass(slots=True)
class RoutingPlan:
    """主路由与影子路由计划"""

    primary: RouteResult
    shadows: tuple[RouteResult, ...] = ()


class RuntimeRouter:
    """运行时路由器"""

    def __init__(self) -> None:
        """初始化运行时路由器"""
        self.matcher = RuleMatcher()

    async def resolve(
            self,
            *,
            model_id: str,
            environment: str,
            subject_key: str | None = None,
            subject_type: str | None = None,
            payload: dict | None = None,
            deployment_id: str | None = None,
            now: datetime | None = None,
            include_shadows: bool = True,
    ) -> RoutingPlan:
        """解析请求路由计划

        主路由按以下优先级解析：
          - 显式指定 deployment_id
          - 运行中的实验分流
          - 启用状态的路由规则
          - 默认活跃部署

        主路由确定后，独立解析满足条件的影子路由。

        参数：
            model_id: 模型 ID
            environment: 部署环境
            subject_key: 分桶主体标识
            subject_type: 分桶主体类型
            payload: 请求负载
            deployment_id: 指定的主部署 ID
            now: 当前时间，默认 UTC 当前时间
            include_shadows: 是否解析影子路由

        返回：
            主路由和影子路由计划

        异常：
            RuntimeRouteError: 无可用部署或路由失败
        """
        current_time = to_utc(
            now or datetime.now(timezone.utc)
        )
        primary = await self._resolve_primary(
            model_id=model_id,
            environment=environment,
            subject_key=subject_key,
            subject_type=subject_type,
            payload=payload,
            deployment_id=deployment_id,
            now=current_time,
        )

        if not include_shadows:
            return RoutingPlan(
                primary=primary
            )

        shadows = await self._resolve_shadows(
            model_id=model_id,
            environment=environment,
            subject_key=subject_key,
            subject_type=subject_type,
            payload=payload,
            primary_deployment_id=primary.deployment_id,
            now=current_time,
        )

        return RoutingPlan(
            primary=primary,
            shadows=tuple(shadows),
        )

    async def _resolve_primary(
            self,
            *,
            model_id: str,
            environment: str,
            subject_key: str | None = None,
            subject_type: str | None = None,
            payload: dict | None = None,
            deployment_id: str | None = None,
            now: datetime | None = None,
    ) -> RouteResult:
        """解析主路由"""
        if not model_id:
            raise RuntimeRouteError("模型 ID 不能为空")

        if not environment:
            raise RuntimeRouteError("部署环境不能为空")

        current_time = to_utc(now or datetime.now(timezone.utc))

        logger.info(
            "开始解析运行时路由",
            model_id=model_id,
            subject_key=subject_key,
            subject_type=subject_type,
            environment=environment,
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)
            routing_repo = RoutingRepository(uow.session)

            if deployment_id is not None:
                return await self._resolve_manual_deployment(
                    deployment_repo=deployment_repo,
                    deployment_id=deployment_id,
                    model_id=model_id,
                    subject_key=subject_key,
                    subject_type=subject_type,
                    environment=environment,
                    now=current_time,
                )

            experiment_result = await self._resolve_ab_test(
                uow=uow,
                deployment_repo=deployment_repo,
                model_id=model_id,
                subject_key=subject_key,
                subject_type=subject_type,
                payload=payload,
                environment=environment,
                now=current_time,
            )

            if experiment_result is not None:
                return experiment_result

            routing_result = await self._resolve_routing(
                deployment_repo=deployment_repo,
                routing_repo=routing_repo,
                model_id=model_id,
                subject_key=subject_key,
                subject_type=subject_type,
                payload=payload,
                environment=environment,
                now=current_time,
            )

            if routing_result is not None:
                return routing_result

            deployment_result = await self._resolve_default_deployment(
                deployment_repo=deployment_repo,
                model_id=model_id,
                subject_key=subject_key,
                subject_type=subject_type,
                environment=environment,
                now=current_time,
            )

            if deployment_result is not None:
                return deployment_result

        raise RuntimeRouteError(
            f"没有可用部署: model_id={model_id}, environment={environment}"
        )

    async def _resolve_manual_deployment(
            self,
            *,
            deployment_repo: DeploymentRepository,
            deployment_id: str,
            model_id: str,
            subject_key: str | None,
            subject_type: str | None,
            environment: str,
            now: datetime,
    ) -> RouteResult:
        """解析指定部署路由"""
        deployment = await deployment_repo.get_deployment(
            deployment_id,
        )

        if deployment is None:
            raise RuntimeRouteError(f"部署不存在: {deployment_id}")

        if deployment.model_id != model_id:
            raise RuntimeRouteError(
                "部署所属模型与请求模型不一致: "
                f"model_id={model_id}, deployment_model_id={deployment.model_id}"
            )

        if self._is_shadow_deployment(
                deployment
        ):
            raise RuntimeRouteError(
                "影子部署不能作为主预测目标: "
                f"{deployment_id}"
            )

        if not self._is_routable_deployment(
                deployment,
                environment=environment,
                now=now,
        ):
            raise RuntimeRouteError(f"部署不可用: {deployment_id}")

        return self._build_deployment_result(
            deployment=deployment,
            source=DecisionStrategy.MANUAL,
            strategy="manual",
            subject_key=subject_key,
            subject_type=subject_type,
            context={
                "reason": "manual_deployment",
            },
        )

    async def _resolve_ab_test(
            self,
            *,
            uow: UnitOfWork,
            deployment_repo: DeploymentRepository,
            model_id: str,
            subject_key: str | None,
            subject_type: str | None,
            payload: dict | None,
            environment: str,
            now: datetime,
    ) -> RouteResult | None:
        """解析 A/B 实验路由"""
        engine = ABTestEngine(
            experiment_repo=ExperimentRepository(uow.session),
            variant_repo=VariantRepository(uow.session),
            assignment_repo=AssignmentRepository(uow.session),
        )

        try:
            result = await engine.assign(
                model_id=model_id,
                environment=environment,
                subject_key=subject_key,
                subject_type=subject_type,
                payload=payload,
                now=now,
                flush=False,
            )
        except ValueError as exc:
            logger.warning(
                "A/B 实验分配失败",
                model_id=model_id,
                environment=environment,
                subject_key=subject_key,
                error=str(exc),
            )
            raise RuntimeRouteError(
                f"A/B 实验分配失败: {exc}"
            ) from exc

        if result is None:
            return None

        deployment = await deployment_repo.get_deployment(
            result.deployment_id,
        )

        if deployment is None:
            logger.warning(
                "实验命中的部署不存在，跳过实验路由",
                experiment_id=result.experiment_id,
                variant_id=result.variant_id,
                deployment_id=result.deployment_id,
            )
            await uow.session.rollback()
            return None

        if deployment.model_id != model_id:
            logger.warning(
                "实验命中的部署所属模型与请求模型不一致，跳过实验路由",
                model_id=model_id,
                deployment_model_id=deployment.model_id,
                deployment_id=deployment.deployment_id,
            )
            await uow.session.rollback()
            return None

        if self._is_shadow_deployment(
                deployment
        ):
            logger.warning(
                "实验分组不能使用影子部署，跳过实验路由",
                experiment_id=result.experiment_id,
                variant_id=result.variant_id,
                deployment_id=deployment.deployment_id,
            )
            await uow.session.rollback()
            return None

        if not self._is_routable_deployment(
                deployment,
                environment=environment,
                now=now,
        ):
            logger.warning(
                "实验命中的部署不可用，跳过实验路由",
                experiment_id=result.experiment_id,
                variant_id=result.variant_id,
                deployment_id=deployment.deployment_id,
                status=deployment.status,
                environment=deployment.environment,
            )
            await uow.session.rollback()
            return None

        return self._build_ab_test_result(
            result=result,
            deployment=deployment,
        )

    async def _resolve_routing(
            self,
            *,
            deployment_repo: DeploymentRepository,
            routing_repo: RoutingRepository,
            model_id: str,
            subject_key: str | None,
            subject_type: str | None,
            payload: dict | None,
            environment: str,
            now: datetime,
    ) -> RouteResult | None:
        """解析 routing 表路由"""
        routings = await routing_repo.list_enabled_routings(
            environment=Environment(
                environment
            ),
        )

        if not routings:
            return None

        candidates: list[tuple[Routing, Deployment]] = []

        for routing in routings:
            if not self._is_effective_routing(
                    routing,
                    now=now,
            ):
                continue

            deployment = await deployment_repo.get_deployment(
                routing.deployment_id,
            )

            if deployment is None:
                continue

            if deployment.model_id != model_id:
                continue

            if self._is_shadow_deployment(
                    deployment
            ):
                continue

            if not self._is_routable_deployment(
                    deployment,
                    environment=environment,
                    now=now,
            ):
                continue

            if routing.rules:
                try:
                    if not self.matcher.match(
                            payload=payload or {},
                            rules=routing.rules,
                    ):
                        continue

                except ValueError as exc:
                    logger.warning(
                        "路由规则匹配失败，跳过该路由",
                        routing_id=routing.routing_id,
                        deployment_id=routing.deployment_id,
                        error=str(exc),
                    )
                    continue

            candidates.append((routing, deployment))

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: str(item[0].routing_id)
        )

        payload_subject_key = self._payload_key(
            payload
        )

        routing_key = (
                subject_key
                or payload_subject_key
                or model_id
        )

        route_subject_key = (
                subject_key
                or payload_subject_key
        )

        ratio, bucket = self._hash_ratio(
            "routing",
            model_id,
            environment,
            routing_key,
        )

        try:
            total_weight = validate_traffic_allocation(
                routing for routing, _ in candidates
            )
        except ValueError as exc:
            raise RuntimeRouteError(str(exc)) from exc

        if total_weight <= 0:
            return None

        point = ratio
        current = 0.0

        for routing, deployment in candidates:
            weight = self._clamp(
                self._safe_float(routing.traffic_ratio, default=0.0),
                0.0,
                1.0,
            )

            current += weight

            if weight > 0 and point < current:
                return self._build_deployment_result(
                    deployment=deployment,
                    source=DecisionStrategy.ROUTING,
                    strategy="weighted",
                    routing_id=routing.routing_id,
                    subject_key=route_subject_key,
                    subject_type=subject_type,
                    bucket=bucket,
                    weight=weight,
                    context={
                        "routing_id": routing.routing_id,
                        "rollout_type": deployment.rollout_type,
                        "rollout_group": deployment.role,
                        "traffic_ratio": routing.traffic_ratio,
                        "rules": routing.rules,
                        "ratio": ratio,
                        "bucket": bucket,
                    },
                )

        return None

    async def _resolve_default_deployment(
            self,
            *,
            deployment_repo: DeploymentRepository,
            model_id: str,
            subject_key: str | None,
            subject_type: str | None,
            environment: str,
            now: datetime,
    ) -> RouteResult | None:
        """解析默认部署路由"""
        deployments = await deployment_repo.list_active_deployments(
            model_id,
            environment=Environment(
                environment
            ),
        )

        deployments = [
            item for item in deployments
            if (
                not self._is_shadow_deployment(item)
                and self._is_routable_deployment(
                    item,
                    environment=environment,
                    now=now,
                )
            )
        ]

        if not deployments:
            return None

        champion = [
            item for item in deployments
            if item.role == DeploymentRole.CHAMPION.value
        ]

        if champion:
            deployment = champion[0]
            fallback_reason = "active_champion_deployment"
        else:
            deployment = deployments[0]
            fallback_reason = "first_active_deployment"

        return self._build_deployment_result(
            deployment=deployment,
            source=DecisionStrategy.DEPLOYMENT,
            strategy="fallback",
            subject_key=subject_key,
            subject_type=subject_type,
            context={
                "reason": fallback_reason,
            },
        )

    async def _resolve_shadows(
            self,
            *,
            model_id: str,
            environment: str,
            subject_key: str | None,
            subject_type: str | None,
            payload: dict | None,
            primary_deployment_id: str,
            now: datetime,
    ) -> list[RouteResult]:
        """解析本次请求命中的影子部署"""
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )
            routing_repo = RoutingRepository(
                uow.session
            )
            routings = await routing_repo.list_enabled_routings(
                environment=Environment(
                    environment
                ),
            )
            route_subject_key = (
                subject_key
                or self._payload_key(payload)
            )
            routing_key = (
                route_subject_key
                or model_id
            )
            results: list[RouteResult] = []
            deployments_seen: set[str] = set()

            for routing in sorted(
                    routings,
                    key=lambda item: str(item.routing_id),
            ):
                deployment = await deployment_repo.get_deployment(
                    routing.deployment_id
                )

                if (
                        deployment is None
                        or not self._is_effective_routing(
                            routing,
                            now=now,
                        )
                        or deployment.model_id != model_id
                        or deployment.deployment_id
                        == primary_deployment_id
                        or deployment.deployment_id
                        in deployments_seen
                        or not self._is_shadow_deployment(
                            deployment
                        )
                        or not self._is_routable_deployment(
                            deployment,
                            environment=environment,
                            now=now,
                        )
                ):
                    continue

                if routing.rules:
                    try:
                        if not self.matcher.match(
                                payload=payload or {},
                                rules=routing.rules,
                        ):
                            continue
                    except ValueError as exc:
                        logger.warning(
                            "影子路由规则匹配失败，跳过该路由",
                            routing_id=routing.routing_id,
                            deployment_id=(
                                routing.deployment_id
                            ),
                            error=str(exc),
                        )
                        continue

                weight = self._clamp(
                    self._safe_float(
                        routing.traffic_ratio,
                        default=0.0,
                    ),
                    0.0,
                    1.0,
                )
                ratio, bucket = self._hash_ratio(
                    "shadow",
                    model_id,
                    environment,
                    str(routing.routing_id),
                    routing_key,
                )

                if weight <= 0 or ratio >= weight:
                    continue

                deployments_seen.add(
                    deployment.deployment_id
                )
                results.append(
                    self._build_deployment_result(
                        deployment=deployment,
                        source=DecisionStrategy.SHADOW,
                        strategy="weighted",
                        routing_id=routing.routing_id,
                        subject_key=route_subject_key,
                        subject_type=subject_type,
                        bucket=bucket,
                        weight=weight,
                        context={
                            "routing_id": routing.routing_id,
                            "rollout_type": (
                                deployment.rollout_type
                            ),
                            "rollout_group": (
                                deployment.role
                            ),
                            "traffic_ratio": (
                                routing.traffic_ratio
                            ),
                            "rules": routing.rules,
                            "ratio": ratio,
                            "bucket": bucket,
                        },
                    )
                )

        return results

    @staticmethod
    def _build_ab_test_result(
            *,
            result: ABTestResult,
            deployment: Deployment,
    ) -> RouteResult:
        """构造 A/B 实验路由结果"""
        duplicate_fields = {
            "assignment_id",
            "bucket",
            "deployment_id",
            "environment",
            "experiment_id",
            "model_id",
            "strategy",
            "subject_key",
            "subject_type",
            "variant_id",
            "variant_name",
            "variant_weight",
        }
        context = {
            key: value
            for key, value in (result.context or {}).items()
            if key not in duplicate_fields
        }
        assignment_source = context.pop(
            "source",
            None,
        )

        if assignment_source in {
            "existing_assignment",
            "new_assignment",
        }:
            context[
                "assignment_source"
            ] = assignment_source

        return RouteResult(
            model_id=deployment.model_id,
            version_id=deployment.version_id,
            deployment_id=deployment.deployment_id,
            framework=deployment.framework,
            environment=deployment.environment,
            source=str(DecisionStrategy.EXPERIMENT),
            strategy=result.strategy,
            experiment_id=result.experiment_id,
            variant_id=result.variant_id,
            assignment_id=result.assignment_id,
            subject_key=result.subject_key,
            subject_type=result.subject_type,
            bucket=result.bucket,
            group=result.group,
            weight=result.weight,
            context=context,
        )

    @staticmethod
    def _build_deployment_result(
            *,
            deployment: Deployment,
            source: DecisionStrategy | str,
            strategy: str,
            routing_id: str | None = None,
            subject_key: str | None = None,
            subject_type: str | None = None,
            bucket: str | None = None,
            weight: float | None = None,
            context: dict | None = None,
    ) -> RouteResult:
        """构造部署路由结果"""
        return RouteResult(
            model_id=deployment.model_id,
            version_id=deployment.version_id,
            deployment_id=deployment.deployment_id,
            framework=deployment.framework,
            environment=deployment.environment,
            source=str(source),
            strategy=strategy,
            routing_id=routing_id,
            subject_key=subject_key,
            subject_type=subject_type,
            bucket=bucket,
            weight=weight,
            context={
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                **(context or {}),
            },
        )

    @staticmethod
    def _payload_key(
            payload: dict | None,
    ) -> str | None:
        """从 payload 中取一个稳定路由键

        说明：
          - A/B 实验分桶主体由 ABTestEngine 根据 bucket_key 解析
          - 这里仅用于 routing 表稳定加权路由
        """
        if not payload:
            return None

        for key in (
                "subject_key",
                "customer_id",
                "order_id",
                "application_id",
        ):
            value = payload.get(key)

            if isinstance(
                    value,
                    (str, bool, int, float),
            ):
                return str(value)

        return None

    def _is_routable_deployment(
            self,
            deployment: Deployment,
            *,
            environment: str,
            now: datetime,
    ) -> bool:
        """判断部署是否可路由"""
        if deployment.status != str(DeploymentStatus.ACTIVE):
            return False

        if deployment.environment != environment:
            return False

        return self._is_effective(deployment, now=now)

    @staticmethod
    def _is_shadow_deployment(
            deployment: Deployment,
    ) -> bool:
        """判断部署是否为影子部署"""
        return (
            deployment.rollout_type
            == RolloutType.SHADOW.value
            or deployment.role
            == DeploymentRole.SHADOW.value
        )

    @staticmethod
    def _is_effective(
            deployment: Deployment,
            *,
            now: datetime,
    ) -> bool:
        """判断部署是否处于生效时间范围"""
        current_time = to_utc(now)
        effective_from = deployment.effective_from
        effective_to = deployment.effective_to

        if effective_from is not None:
            effective_from = to_utc(effective_from)

            if effective_from > current_time:
                return False

        if effective_to is not None:
            effective_to = to_utc(effective_to)

            if effective_to <= current_time:
                return False

        return True

    @staticmethod
    def _is_effective_routing(
            routing: Routing,
            *,
            now: datetime,
    ) -> bool:
        """判断路由是否处于生效时间范围。"""
        current_time = to_utc(now)
        effective_from = getattr(routing, "effective_from", None)
        effective_to = getattr(routing, "effective_to", None)

        if (
                isinstance(effective_from, datetime)
                and to_utc(effective_from) > current_time
        ):
            return False

        if (
                isinstance(effective_to, datetime)
                and to_utc(effective_to) <= current_time
        ):
            return False

        return True

    @staticmethod
    def _hash_ratio(
            *parts: str,
    ) -> tuple[float, str]:
        """计算稳定哈希比例

        返回：
            ratio: 0 到 1 之间的小数
            bucket: 分桶标识
        """
        raw = ":".join(str(part) for part in parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        value = int(digest[:12], 16)
        max_value = int("f" * 12, 16)

        ratio = value / max_value
        bucket = f"bucket_{int(ratio * 10000):04d}"

        return ratio, bucket

    @staticmethod
    def _safe_float(
            value,
            *,
            default: float,
    ) -> float:
        """安全转换 float"""
        if value is None:
            return default

        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(
            value: float,
            min_value: float,
            max_value: float,
    ) -> float:
        """限制数值范围"""
        return max(min_value, min(max_value, value))
