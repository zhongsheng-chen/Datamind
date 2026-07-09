# datamind/runtime/router.py

"""运行时路由器

根据请求上下文选择最终命中的部署 ID。

核心功能：
  - resolve: 解析请求应该命中的部署

说明：
  - 优先命中运行中的实验
  - 其次命中启用的路由规则
  - 最后回退到启用状态的 champion 部署

使用示例：
  from datamind.runtime.router import RuntimeRouter

  router = RuntimeRouter()

  route = await router.resolve(
      model_id="mdl_a1b2c3d4",
      environment="production",
      subject_key="customer_10001",
      subject_type="customer",
      payload={
          "age": 0.35,
          "income": 0.72,
          "gender": 0.10,
          "province": 0.65,
          "education": 0.80,
      }
  )

  print(route.deployment_id)
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from datamind.ab_test.engine import ABTestEngine, ABTestResult
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
    AssignmentStrategy,
    DecisionStrategy,
    DeploymentStatus,
)
from datamind.models.errors import RuntimeRouteError
from datamind.utils.datetime import to_utc

logger = structlog.get_logger(__name__)

CHAMPION_ROLE = "champion"


@dataclass(slots=True)
class RouteResult:
    """路由结果

    属性：
        model_id: 模型 ID
        version_id: 版本 ID
        deployment_id: 部署 ID
        framework: 框架类型
        source: 路由来源，可选值 experiment / routing / deployment / manual
        strategy: 路由策略，例如 hash / weighted / fallback / manual
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


class RuntimeRouter:
    """运行时路由器"""

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
    ) -> RouteResult:
        """解析请求路由

        参数：
            model_id: 模型 ID
            environment: 部署环境
            subject_key: 分桶主体标识，例如客户号、订单号、申请单号。
                如果传入该参数，则 A/B 实验优先使用该值。
            subject_type: 分桶主体类型，例如 customer / order / application
            payload: 请求负载。未传 subject_key 时，A/B 实验会根据实验配置中的
                bucket_key 从 payload 中提取分桶主体标识。
            deployment_id: 指定部署 ID。传入时直接校验并命中该部署
            now: 当前时间，默认 UTC 当前时间

        返回：
            路由结果

        异常：
            RuntimeRouteError: 无可用部署或路由失败
        """
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
                subject_key=subject_key,
                subject_type=subject_type,
                payload=payload,
                now=now,
                flush=False,
            )
        except ValueError as exc:
            logger.warning(
                "A/B 实验分配失败，跳过实验路由",
                model_id=model_id,
                subject_key=subject_key,
                error=str(exc),
            )
            return None

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
            environment=environment,
        )

        if not routings:
            return None

        candidates: list[tuple[Routing, Deployment]] = []

        for routing in routings:
            deployment = await deployment_repo.get_deployment(
                routing.deployment_id,
            )

            if deployment is None:
                continue

            if deployment.model_id != model_id:
                continue

            if not self._is_routable_deployment(
                    deployment,
                    environment=environment,
                    now=now,
            ):
                continue

            candidates.append((routing, deployment))

        if not candidates:
            return None

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

        total_weight = sum(
            self._clamp(
                self._safe_float(routing.traffic_ratio, default=0.0),
                0.0,
                1.0,
            )
            for routing, _ in candidates
        )

        if total_weight <= 0:
            return None

        point = ratio * total_weight
        current = 0.0

        for routing, deployment in candidates:
            weight = self._clamp(
                self._safe_float(routing.traffic_ratio, default=0.0),
                0.0,
                1.0,
            )

            current += weight

            if point <= current:
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
                        "rollout_type": routing.rollout_type,
                        "rollout_group": routing.rollout_group,
                        "traffic_ratio": routing.traffic_ratio,
                        "rules": routing.rules,
                        "ratio": ratio,
                        "bucket": bucket,
                    },
                )

        routing, deployment = candidates[-1]

        return self._build_deployment_result(
            deployment=deployment,
            source=DecisionStrategy.ROUTING,
            strategy="weighted",
            routing_id=routing.routing_id,
            subject_key=route_subject_key,
            subject_type=subject_type,
            bucket=bucket,
            weight=self._safe_float(routing.traffic_ratio, default=0.0),
            context={
                "routing_id": routing.routing_id,
                "rollout_type": routing.rollout_type,
                "rollout_group": routing.rollout_group,
                "traffic_ratio": routing.traffic_ratio,
                "rules": routing.rules,
                "ratio": ratio,
                "bucket": bucket,
                "fallback": "last_candidate",
            },
        )

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
            environment=environment,
        )

        deployments = [
            item for item in deployments
            if self._is_routable_deployment(
                item,
                environment=environment,
                now=now,
            )
        ]

        if not deployments:
            return None

        champion = [
            item for item in deployments
            if item.role == CHAMPION_ROLE
        ]

        if champion:
            deployment = champion[0]
        else:
            deployment = deployments[0]

        return self._build_deployment_result(
            deployment=deployment,
            source=DecisionStrategy.DEPLOYMENT,
            strategy="fallback",
            subject_key=subject_key,
            subject_type=subject_type,
            context={
                "reason": "active_champion_deployment",
            },
        )

    def _build_ab_test_result(
            self,
            *,
            result: ABTestResult,
            deployment: Deployment,
    ) -> RouteResult:
        """构造 A/B 实验路由结果"""
        return RouteResult(
            model_id=deployment.model_id,
            version_id=deployment.version_id,
            deployment_id=deployment.deployment_id,
            framework=deployment.framework,
            source=DecisionStrategy.EXPERIMENT,
            strategy=AssignmentStrategy.HASH,
            experiment_id=result.experiment_id,
            variant_id=result.variant_id,
            assignment_id=result.assignment_id,
            subject_key=result.subject_key,
            subject_type=result.subject_type,
            bucket=result.bucket,
            group=result.group,
            weight=result.weight,
            context={
                "source": "ab_test_engine",
                "experiment_id": result.experiment_id,
                "variant_id": result.variant_id,
                "variant_name": result.group,
                "deployment_id": deployment.deployment_id,
                **(result.context or {}),
            },
        )

    def _build_deployment_result(
            self,
            *,
            deployment: Deployment,
            source: str,
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
            source=source,
            strategy=strategy,
            routing_id=routing_id,
            subject_key=subject_key,
            subject_type=subject_type,
            bucket=bucket,
            weight=weight,
            context={
                "deployment_id": deployment.deployment_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                **(context or {}),
            },
        )

    def _payload_key(
            self,
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
                "apply_id",
                "application_id",
        ):
            value = payload.get(key)

            if value is not None:
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
        if deployment.status != DeploymentStatus.ACTIVE:
            return False

        if deployment.environment != environment:
            return False

        return self._is_effective(deployment, now=now)

    def _is_effective(
            self,
            obj,
            *,
            now: datetime,
    ) -> bool:
        """判断对象是否处于生效时间范围"""
        current_time = to_utc(now)
        effective_from = getattr(obj, "effective_from", None)
        effective_to = getattr(obj, "effective_to", None)

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
            return float(value)
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
