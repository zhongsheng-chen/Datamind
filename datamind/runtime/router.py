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
      subject_key="customer_10001",
      environment="production",
      payload={
          "customer_id": "customer_10001",
          "age": 35,
      }
  )

  print(route.deployment_id)
"""

import hashlib
import structlog
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from datamind.db.core import UnitOfWork
from datamind.db.models.deployments import Deployment
from datamind.db.models.experiments import Experiment
from datamind.db.models.routing import Routing
from datamind.db.models.variants import Variant
from datamind.db.repositories import (
    AssignmentRepository,
    DeploymentRepository,
    ExperimentRepository,
    RoutingRepository,
    VariantRepository,
)
from datamind.models.enums import AssignmentStrategy
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


class RuntimeRouteError(RuntimeError):
    """运行时路由异常"""


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
        subject_key: str | None = None,
        subject_type: str | None = None,
        payload: dict | None = None,
        environment: str = "production",
        deployment_id: str | None = None,
        now: datetime | None = None,
    ) -> RouteResult:
        """解析请求路由

        参数：
            model_id: 模型 ID
            subject_key: 分桶主体标识，例如客户号、订单号、申请单号
            subject_type: 分桶主体类型，例如 customer / order / application
            payload: 请求负载，用于根据实验 bucket_key 提取 subject_key
            environment: 部署环境，默认 production
            deployment_id: 指定部署 ID。传入时直接校验并命中该部署
            now: 当前时间，默认 UTC 当前时间

        返回：
            路由结果

        异常：
            RuntimeRouteError: 无可用部署或路由失败
        """
        current_time = now or datetime.now(timezone.utc)

        logger.info(
            "开始解析运行时路由",
            model_id=model_id,
            subject_key=subject_key,
            subject_type=subject_type,
            environment=environment,
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            assignment_repo = AssignmentRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            experiment_repo = ExperimentRepository(uow.session)
            routing_repo = RoutingRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            if deployment_id is not None:
                return await self._resolve_manual_deployment(
                    deployment_repo=deployment_repo,
                    deployment_id=deployment_id,
                    model_id=model_id,
                    environment=environment,
                    now=current_time,
                )

            experiment_result = await self._resolve_experiment(
                assignment_repo=assignment_repo,
                deployment_repo=deployment_repo,
                experiment_repo=experiment_repo,
                variant_repo=variant_repo,
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
                payload=payload,
                environment=environment,
                now=current_time,
            )

            if routing_result is not None:
                return routing_result

            deployment_result = await self._resolve_default_deployment(
                deployment_repo=deployment_repo,
                model_id=model_id,
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
        environment: str,
        now: datetime,
    ) -> RouteResult:
        """解析指定部署路由"""
        deployment = await deployment_repo.get_deployment(deployment_id)

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
            source="manual",
            strategy="manual",
            context={
                "reason": "manual_deployment",
            },
        )

    async def _resolve_experiment(
        self,
        *,
        assignment_repo: AssignmentRepository,
        deployment_repo: DeploymentRepository,
        experiment_repo: ExperimentRepository,
        variant_repo: VariantRepository,
        model_id: str,
        subject_key: str | None,
        subject_type: str | None,
        payload: dict | None,
        environment: str,
        now: datetime,
    ) -> RouteResult | None:
        """解析实验路由"""
        experiments = await experiment_repo.list_running_experiments(model_id)

        if not experiments:
            return None

        experiments = [
            item for item in experiments
            if self._is_effective(item, now=now)
        ]

        experiments.sort(
            key=lambda item: item.updated_at or item.created_at,
            reverse=True,
        )

        for experiment in experiments:
            config = experiment.config or {}

            actual_subject_key = self._resolve_subject_key(
                subject_key=subject_key,
                payload=payload,
                bucket_key=config.get("bucket_key"),
            )

            if actual_subject_key is None:
                logger.info(
                    "实验缺少分桶主体标识，跳过实验路由",
                    experiment_id=experiment.experiment_id,
                    model_id=model_id,
                )
                continue

            assignment = await assignment_repo.get_subject_assignment(
                experiment_id=experiment.experiment_id,
                subject_key=actual_subject_key,
            )

            if assignment is not None:
                result = await self._resolve_existing_assignment(
                    deployment_repo=deployment_repo,
                    variant_repo=variant_repo,
                    experiment=experiment,
                    assignment=assignment,
                    subject_key=actual_subject_key,
                    subject_type=subject_type,
                    environment=environment,
                    now=now,
                )

                if result is not None:
                    return result

                continue

            traffic_ratio = self._safe_float(
                config.get("traffic_ratio"),
                default=1.0,
            )

            traffic_ratio = self._clamp(traffic_ratio, 0.0, 1.0)

            exposure_ratio, exposure_bucket = self._hash_ratio(
                "experiment_exposure",
                experiment.experiment_id,
                actual_subject_key,
            )

            if exposure_ratio > traffic_ratio:
                logger.info(
                    "主体未进入实验曝光流量",
                    experiment_id=experiment.experiment_id,
                    subject_key=actual_subject_key,
                    exposure_ratio=exposure_ratio,
                    traffic_ratio=traffic_ratio,
                )
                continue

            variants = await variant_repo.list_active_variants(
                experiment.experiment_id,
            )

            routable_variants = await self._filter_routable_variants(
                variants=variants,
                deployment_repo=deployment_repo,
                model_id=model_id,
                environment=environment,
                now=now,
            )

            if not routable_variants:
                logger.warning(
                    "实验没有可路由分组",
                    experiment_id=experiment.experiment_id,
                    model_id=model_id,
                )
                continue

            variant, deployment, variant_ratio, variant_bucket = self._choose_variant(
                experiment=experiment,
                variants=routable_variants,
                subject_key=actual_subject_key,
            )

            assignment = assignment_repo.create_assignment(
                assignment_id=generate_random_id(prefix="asn"),
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                subject_key=actual_subject_key,
                subject_type=subject_type,
                strategy=AssignmentStrategy.HASH,
                bucket=variant_bucket,
                weight=variant.weight,
                context={
                    "source": "experiment",
                    "strategy": config.get("strategy", "hash"),
                    "bucket_key": config.get("bucket_key"),
                    "traffic_ratio": traffic_ratio,
                    "exposure_ratio": exposure_ratio,
                    "exposure_bucket": exposure_bucket,
                    "variant_ratio": variant_ratio,
                    "variant_bucket": variant_bucket,
                    "variant_name": variant.name,
                    "deployment_id": deployment.deployment_id,
                },
            )

            return self._build_experiment_result(
                experiment=experiment,
                variant=variant,
                deployment=deployment,
                assignment_id=assignment.assignment_id,
                subject_key=actual_subject_key,
                subject_type=subject_type,
                bucket=variant_bucket,
                context={
                    "new_assignment": True,
                    "traffic_ratio": traffic_ratio,
                    "exposure_ratio": exposure_ratio,
                    "exposure_bucket": exposure_bucket,
                    "variant_ratio": variant_ratio,
                },
            )

        return None

    async def _resolve_existing_assignment(
        self,
        *,
        deployment_repo: DeploymentRepository,
        variant_repo: VariantRepository,
        experiment: Experiment,
        assignment,
        subject_key: str,
        subject_type: str | None,
        environment: str,
        now: datetime,
    ) -> RouteResult | None:
        """根据已有实验分配解析路由"""
        variant = await variant_repo.get_variant(assignment.variant_id)

        if variant is None:
            logger.warning(
                "实验分配对应的分组不存在",
                experiment_id=experiment.experiment_id,
                variant_id=assignment.variant_id,
                assignment_id=assignment.assignment_id,
            )
            return None

        if self._value(variant.status) != "active":
            logger.warning(
                "实验分配对应的分组不是启用状态",
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                status=variant.status,
            )
            return None

        deployment = await deployment_repo.get_deployment(variant.deployment_id)

        if deployment is None:
            logger.warning(
                "实验分组对应的部署不存在",
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                deployment_id=variant.deployment_id,
            )
            return None

        if not self._is_routable_deployment(
            deployment,
            environment=environment,
            now=now,
        ):
            logger.warning(
                "实验分组对应的部署不可用",
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                deployment_id=deployment.deployment_id,
            )
            return None

        return self._build_experiment_result(
            experiment=experiment,
            variant=variant,
            deployment=deployment,
            assignment_id=assignment.assignment_id,
            subject_key=subject_key,
            subject_type=subject_type,
            bucket=assignment.bucket,
            context={
                "new_assignment": False,
                "assignment_id": assignment.assignment_id,
            },
        )

    async def _resolve_routing(
        self,
        *,
        deployment_repo: DeploymentRepository,
        routing_repo: RoutingRepository,
        model_id: str,
        subject_key: str | None,
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

        routing_key = subject_key or self._payload_key(payload) or model_id

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
                    source="routing",
                    strategy="weighted",
                    routing_id=routing.routing_id,
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
            source="routing",
            strategy="weighted",
            routing_id=routing.routing_id,
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
            if self._value(item.role) == "champion"
        ]

        if champion:
            deployment = champion[0]
        else:
            deployment = deployments[0]

        return self._build_deployment_result(
            deployment=deployment,
            source="deployment",
            strategy="fallback",
            context={
                "reason": "active_champion_deployment",
            },
        )

    async def _filter_routable_variants(
        self,
        *,
        variants: list[Variant],
        deployment_repo: DeploymentRepository,
        model_id: str,
        environment: str,
        now: datetime,
    ) -> list[tuple[Variant, Deployment]]:
        """过滤可路由实验分组"""
        result: list[tuple[Variant, Deployment]] = []

        for variant in variants:
            deployment = await deployment_repo.get_deployment(
                variant.deployment_id,
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

            result.append((variant, deployment))

        return result

    def _choose_variant(
        self,
        *,
        experiment: Experiment,
        variants: list[tuple[Variant, Deployment]],
        subject_key: str,
    ) -> tuple[Variant, Deployment, float, str]:
        """根据权重选择实验分组"""
        total_weight = sum(
            self._clamp(
                self._safe_float(variant.weight, default=0.0),
                0.0,
                1.0,
            )
            for variant, _ in variants
        )

        if total_weight <= 0:
            raise RuntimeRouteError(
                f"实验没有有效分组权重: {experiment.experiment_id}"
            )

        ratio, bucket = self._hash_ratio(
            "experiment_variant",
            experiment.experiment_id,
            subject_key,
        )

        point = ratio * total_weight
        current = 0.0

        for variant, deployment in variants:
            current += self._clamp(
                self._safe_float(variant.weight, default=0.0),
                0.0,
                1.0,
            )

            if point <= current:
                return variant, deployment, ratio, bucket

        variant, deployment = variants[-1]
        return variant, deployment, ratio, bucket

    def _build_experiment_result(
        self,
        *,
        experiment: Experiment,
        variant: Variant,
        deployment: Deployment,
        assignment_id: str | None,
        subject_key: str,
        subject_type: str | None,
        bucket: str | None,
        context: dict | None = None,
    ) -> RouteResult:
        """构造实验路由结果"""
        return RouteResult(
            model_id=deployment.model_id,
            version_id=deployment.version_id,
            deployment_id=deployment.deployment_id,
            framework=deployment.framework,
            source="experiment",
            strategy=(experiment.config or {}).get("strategy", "hash"),
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            assignment_id=assignment_id,
            subject_key=subject_key,
            subject_type=subject_type,
            bucket=bucket,
            group=variant.name,
            weight=variant.weight,
            context={
                "experiment_id": experiment.experiment_id,
                "experiment_name": experiment.name,
                "variant_id": variant.variant_id,
                "variant_name": variant.name,
                "is_control": variant.is_control,
                "deployment_id": deployment.deployment_id,
                **(context or {}),
            },
        )

    def _build_deployment_result(
        self,
        *,
        deployment: Deployment,
        source: str,
        strategy: str,
        routing_id: str | None = None,
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

    def _resolve_subject_key(
        self,
        *,
        subject_key: str | None,
        payload: dict | None,
        bucket_key: str | None,
    ) -> str | None:
        """解析分桶主体标识"""
        if subject_key:
            return subject_key

        if not payload:
            return None

        if not bucket_key:
            return None

        value = payload.get(bucket_key)

        if value is None:
            return None

        return str(value)

    def _payload_key(
        self,
        payload: dict | None,
    ) -> str | None:
        """从 payload 中取一个稳定路由键"""
        if not payload:
            return None

        for key in ("customer_id", "order_id", "apply_id", "application_id", "subject_key"):
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
        if self._value(deployment.status) != "active":
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
        effective_from = getattr(obj, "effective_from", None)
        effective_to = getattr(obj, "effective_to", None)

        if effective_from is not None and now < effective_from:
            return False

        if effective_to is not None and now > effective_to:
            return False

        return True

    def _hash_ratio(
        self,
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

    def _safe_float(
        self,
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

    def _clamp(
        self,
        value: float,
        min_value: float,
        max_value: float,
    ) -> float:
        """限制数值范围"""
        return max(min_value, min(max_value, value))

    def _value(
        self,
        value,
    ) -> str:
        """兼容字符串和枚举值"""
        if hasattr(value, "value"):
            return str(value.value)

        return str(value)