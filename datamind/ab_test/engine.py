"""A/B 实验执行引擎.

负责在请求进入模型推理前，根据运行中的实验配置、实验分组和固定分配记录，
确定当前请求是否命中 A/B 实验，以及命中哪个实验分组。

核心功能：
  - ABTestResult: A/B 实验命中结果
  - ABTestEngine: A/B 实验执行引擎

使用示例：
  from datamind.ab_test.engine import ABTestEngine
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import (
      AssignmentRepository,
      ExperimentRepository,
      VariantRepository
  )

  async with UnitOfWork() as uow:
      engine = ABTestEngine(
          experiment_repo=ExperimentRepository(uow.session),
          variant_repo=VariantRepository(uow.session),
          assignment_repo=AssignmentRepository(uow.session)
      )

      assignment = await engine.assign(
          model_id="mdl_0123456789abcdef",
          environment="development",
          subject_key="customer_10001",
          subject_type="customer"
      )
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from datamind.ab_test.assignment import AssignmentResult, ExperimentAssigner
from datamind.constants import Environment
from datamind.db.models.assignments import Assignment
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.db.repositories.assignment import AssignmentRepository
from datamind.db.repositories.experiment import ExperimentRepository
from datamind.db.repositories.variant import VariantRepository
from datamind.models.enums import (
    AssignmentStrategy,
    DecisionStrategy,
    ExperimentVariantStatus,
)
from datamind.utils.datetime import to_utc
from datamind.utils.generator import generate_random_id


@dataclass(slots=True)
class ABTestResult:
    """A/B 实验命中结果.

    属性：
        experiment_id: 实验 ID
        variant_id: 实验分组 ID
        deployment_id: 命中的部署 ID
        assignment_id: 实验固定分配 ID
        model_id: 模型 ID
        environment: 实验环境
        subject_key: 分桶主体标识
        subject_type: 分桶主体类型
        source: 命中来源，固定为 experiment
        strategy: 分配策略
        bucket: 分桶标识
        group: 实验分组名称
        weight: 命中分组权重
        experiment: 实验对象
        variant: 实验分组对象
        assignment: 实验分配对象
        context: 实验命中上下文
    """

    experiment_id: str
    variant_id: str
    deployment_id: str
    assignment_id: str
    model_id: str
    environment: str
    subject_key: str
    subject_type: str | None
    source: str
    strategy: str
    bucket: str | None
    group: str | None
    weight: float | None
    experiment: Experiment
    variant: Variant
    assignment: Assignment
    context: dict


class ABTestEngine:
    """A/B 实验执行引擎.

    根据模型 ID 和环境查询运行中的实验，
    再根据 subject_key 判断是否进入实验，并分配到实验分组。

    说明：
      - 同一个 model_id 在同一 environment 下，只允许一个有效 running 实验参与分流
      - hash 策略使用 traffic_ratio 和 Variant weight 稳定分配
      - manual 策略使用调用方指定的 Variant
      - 已存在固定分配记录时，优先使用固定分配结果
    """

    def __init__(
            self,
            *,
            experiment_repo: ExperimentRepository,
            variant_repo: VariantRepository,
            assignment_repo: AssignmentRepository,
            assigner: ExperimentAssigner | None = None,
    ):
        """初始化 A/B 实验执行引擎.

        参数：
            experiment_repo: 实验仓储
            variant_repo: 实验分组仓储
            assignment_repo: 实验分配仓储
            assigner: 实验分配器，默认使用 ExperimentAssigner
        """
        self.experiment_repo = experiment_repo
        self.variant_repo = variant_repo
        self.assignment_repo = assignment_repo
        self.assigner = assigner or ExperimentAssigner()

    async def assign(
            self,
            *,
            model_id: str,
            environment: str,
            subject_key: str | None = None,
            subject_type: str | None = None,
            payload: dict | None = None,
            manual_variant_id: str | None = None,
            manual_variant_name: str | None = None,
            manual_assignments: dict[str, Any] | None = None,
            now: datetime | None = None,
            flush: bool = False,
    ) -> ABTestResult | None:
        """分配 A/B 实验分组.

        参数：
            model_id: 模型 ID
            environment: 实验环境
            subject_key: 分桶主体标识，例如客户号、订单号、申请单号。
                如果传入该参数，则优先使用该值。
            subject_type: 分桶主体类型（可选）
            payload: 请求负载。未传 subject_key 时，会根据实验配置中的 bucket_key
                从 payload 中提取分桶主体标识。
            manual_variant_id: 手工指定的 Variant ID，manual 策略使用
            manual_variant_name: 手工指定的 Variant 名称，manual 策略使用
            manual_assignments: subject_key 到 Variant 的映射关系，manual 策略使用
            now: 当前时间（可选）
            flush: 是否立即 flush 到数据库，默认 False

        返回：
            A/B 实验命中结果；如果没有命中实验，返回 None

        异常：
            ValueError: 参数或实验配置非法
        """
        if not model_id:
            raise ValueError("模型 ID 不能为空")

        if not environment:
            raise ValueError("实验环境不能为空")

        if subject_key is None and payload is None:
            raise ValueError("分桶主体不能为空")

        current_time = to_utc(now or datetime.now(timezone.utc))

        experiments = await self.experiment_repo.list_running_experiments(
            model_id=model_id,
            environment=Environment(
                environment
            ),
            now=current_time,
        )

        if len(experiments) > 1:
            raise ValueError(
                "模型在当前环境下存在多个运行中的实验，无法确定实验分流规则"
            )

        for experiment in experiments:
            if not self._is_effective(experiment, current_time):
                continue

            config = self._get_config(experiment)

            strategy = self._get_experiment_strategy(experiment)

            actual_subject_key = self._resolve_subject_key(
                subject_key=subject_key,
                payload=payload,
                bucket_key=config.get("bucket_key"),
            )

            if actual_subject_key is None:
                continue

            assignment = await self.assignment_repo.get_subject_assignment(
                experiment_id=experiment.experiment_id,
                subject_key=actual_subject_key,
            )

            if assignment is not None:
                result = await self._build_existing_result(
                    experiment=experiment,
                    assignment=assignment,
                    subject_type=subject_type,
                )

                if result is not None:
                    return result

                continue

            variants = await self.variant_repo.list_active_variants(
                experiment_id=experiment.experiment_id,
            )

            traffic_ratio = 1.0

            if strategy == AssignmentStrategy.HASH:
                traffic_ratio = self._get_traffic_ratio(experiment)

            assignment_result = self.assigner.assign(
                strategy=strategy,
                experiment_id=experiment.experiment_id,
                subject_key=actual_subject_key,
                traffic_ratio=traffic_ratio,
                variants=variants,
                manual_variant_id=self._get_manual_variant_id(
                    config=config,
                    payload=payload,
                    manual_variant_id=manual_variant_id,
                ),
                manual_variant_name=self._get_manual_variant_name(
                    config=config,
                    payload=payload,
                    manual_variant_name=manual_variant_name,
                ),
                manual_assignments=self._get_manual_assignments(
                    config=config,
                    payload=payload,
                    manual_assignments=manual_assignments,
                ),
            )

            if assignment_result is None:
                continue

            assignment_context = dict(assignment_result.context)
            assignment_context.update(
                {
                    "model_id": model_id,
                    "environment": environment,
                    "bucket_key": config.get("bucket_key"),
                    "strategy": str(strategy),
                }
            )

            assignment, created = (
                await self.assignment_repo.get_or_create_assignment(
                assignment_id=generate_random_id(
                    prefix="asn"
                ),
                experiment_id=experiment.experiment_id,
                variant_id=assignment_result.variant.variant_id,
                subject_key=actual_subject_key,
                subject_type=subject_type,
                strategy=strategy,
                bucket=assignment_result.bucket,
                weight=float(assignment_result.variant.weight),
                context=assignment_context,
                assigned_at=current_time,
                )
            )

            if flush:
                await self.assignment_repo.flush()

            if not created:
                return await self._build_existing_result(
                    experiment=experiment,
                    assignment=assignment,
                    subject_type=subject_type,
                )

            return self._build_new_result(
                experiment=experiment,
                assignment=assignment,
                assignment_result=assignment_result,
                subject_type=subject_type,
            )

        return None

    async def _build_existing_result(
            self,
            *,
            experiment: Experiment,
            assignment: Assignment,
            subject_type: str | None,
    ) -> ABTestResult | None:
        """根据已有固定分配构造实验命中结果.

        参数：
            experiment: 实验对象
            assignment: 实验分配对象
            subject_type: 分桶主体类型（可选）

        返回：
            A/B 实验命中结果；如果分组不存在或不可用，返回 None
        """
        variant = await self.variant_repo.get_variant(assignment.variant_id)

        if variant is None:
            return None

        if variant.status != str(ExperimentVariantStatus.ACTIVE):
            return None

        strategy = self._assignment_strategy_value(
            assignment.strategy
        )

        context = dict(assignment.context or {})
        context.update(
            {
                "source": "existing_assignment",
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "environment": experiment.environment,
                "variant_id": variant.variant_id,
                "variant_name": variant.name,
                "deployment_id": variant.deployment_id,
                "assignment_id": assignment.assignment_id,
                "subject_key": assignment.subject_key,
                "subject_type": subject_type or assignment.subject_type,
                "strategy": strategy,
            }
        )
        if assignment.bucket is not None:
            context["bucket"] = assignment.bucket

        return ABTestResult(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            deployment_id=variant.deployment_id,
            assignment_id=assignment.assignment_id,
            model_id=experiment.model_id,
            environment=experiment.environment,
            subject_key=assignment.subject_key,
            subject_type=subject_type or assignment.subject_type,
            source=str(DecisionStrategy.EXPERIMENT),
            strategy=strategy,
            bucket=assignment.bucket,
            group=variant.name,
            weight=assignment.weight,
            experiment=experiment,
            variant=variant,
            assignment=assignment,
            context=context,
        )

    @staticmethod
    def _build_new_result(
            *,
            experiment: Experiment,
            assignment: Assignment,
            assignment_result: AssignmentResult,
            subject_type: str | None,
    ) -> ABTestResult:
        """根据新分配结果构造实验命中结果.

        参数：
            experiment: 实验对象
            assignment: 实验分配对象
            assignment_result: 实验分配结果
            subject_type: 分桶主体类型（可选）

        返回：
            A/B 实验命中结果
        """
        variant = assignment_result.variant
        strategy = ABTestEngine._assignment_strategy_value(
            assignment.strategy
        )

        context = dict(assignment.context or assignment_result.context)
        context.update(
            {
                "source": "new_assignment",
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "environment": experiment.environment,
                "variant_id": variant.variant_id,
                "variant_name": variant.name,
                "deployment_id": variant.deployment_id,
                "assignment_id": assignment.assignment_id,
                "subject_key": assignment.subject_key,
                "subject_type": subject_type,
                "strategy": strategy,
            }
        )
        if assignment_result.bucket is not None:
            context["bucket"] = assignment_result.bucket

        return ABTestResult(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            deployment_id=variant.deployment_id,
            assignment_id=assignment.assignment_id,
            model_id=experiment.model_id,
            environment=experiment.environment,
            subject_key=assignment.subject_key,
            subject_type=subject_type,
            source=str(DecisionStrategy.EXPERIMENT),
            strategy=strategy,
            bucket=assignment_result.bucket,
            group=variant.name,
            weight=float(variant.weight),
            experiment=experiment,
            variant=variant,
            assignment=assignment,
            context=context,
        )

    @classmethod
    def _get_traffic_ratio(cls, experiment: Experiment) -> float:
        """获取实验曝光比例.

        参数：
            experiment: 实验对象

        返回：
            实验曝光比例，取值范围为 (0, 1]

        异常：
            ValueError: 实验配置非法
        """
        config = cls._get_config(experiment)

        traffic_ratio = float(config.get("traffic_ratio", 1.0))

        if not math.isfinite(traffic_ratio):
            raise ValueError("实验曝光比例必须是有限数值")

        if traffic_ratio <= 0:
            raise ValueError("实验曝光比例必须大于 0")

        if traffic_ratio > 1:
            raise ValueError("实验曝光比例不能大于 1")

        return traffic_ratio

    @classmethod
    def _get_experiment_strategy(
            cls,
            experiment: Experiment,
    ) -> AssignmentStrategy:
        """获取实验分配策略.

        参数：
            experiment: 实验对象

        返回：
            AssignmentStrategy 枚举值

        异常：
            ValueError: 实验分配策略非法
        """
        config = cls._get_config(experiment)

        strategy = (
                config.get("strategy")
                or AssignmentStrategy.HASH
        )

        strategy = str(strategy).lower()

        try:
            return AssignmentStrategy(strategy)

        except ValueError as exc:
            raise ValueError(
                f"不支持的实验分配策略: {strategy}"
            ) from exc

    @staticmethod
    def _get_config(experiment: Experiment) -> dict:
        """获取实验配置.

        参数：
            experiment: 实验对象

        返回：
            实验配置字典

        异常：
            ValueError: 实验配置非法
        """
        config = experiment.config or {}

        if not isinstance(config, dict):
            raise ValueError("实验配置 config 必须是 JSON 对象")

        return config

    @staticmethod
    def _get_manual_variant_id(
            *,
            config: dict,
            payload: dict | None,
            manual_variant_id: str | None,
    ) -> str | None:
        """获取手工指定 Variant ID.

        参数：
            config: 实验配置
            payload: 请求负载
            manual_variant_id: 外部直接传入的 Variant ID

        返回：
            Variant ID
        """
        if manual_variant_id:
            return manual_variant_id

        value = config.get("manual_variant_id")

        if isinstance(value, str) and value:
            return value

        if not payload:
            return None

        value = payload.get("manual_variant_id")

        if isinstance(value, str) and value:
            return value

        return None

    @staticmethod
    def _get_manual_variant_name(
            *,
            config: dict,
            payload: dict | None,
            manual_variant_name: str | None,
    ) -> str | None:
        """获取手工指定 Variant 名称.

        参数：
            config: 实验配置
            payload: 请求负载
            manual_variant_name: 外部直接传入的 Variant 名称

        返回：
            Variant 名称
        """
        if manual_variant_name:
            return manual_variant_name

        value = config.get("manual_variant_name")

        if isinstance(value, str) and value:
            return value

        if not payload:
            return None

        value = payload.get("manual_variant_name")

        if isinstance(value, str) and value:
            return value

        return None

    @staticmethod
    def _get_manual_assignments(
            *,
            config: dict,
            payload: dict | None,
            manual_assignments: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """获取手工指定分组映射关系.

        参数：
            config: 实验配置
            payload: 请求负载
            manual_assignments: 外部直接传入的映射关系

        返回：
            subject_key 到 Variant 的映射关系
        """
        if manual_assignments is not None:
            return manual_assignments

        value = config.get("manual_assignments")

        if isinstance(value, dict):
            return value

        if not payload:
            return None

        value = payload.get("manual_assignments")

        if isinstance(value, dict):
            return value

        return None

    @staticmethod
    def _resolve_subject_key(
            *,
            subject_key: str | None,
            payload: dict | None,
            bucket_key: str | None,
    ) -> str | None:
        """解析分桶主体标识.

        参数：
            subject_key: 外部直接传入的分桶主体标识
            payload: 请求负载
            bucket_key: 实验配置中的分桶主体字段

        返回：
            分桶主体标识；无法解析时返回 None
        """
        if subject_key:
            return subject_key

        if not payload:
            return None

        if not bucket_key:
            return None

        value = payload.get(bucket_key)

        if isinstance(value, str):
            return value or None

        if (
                isinstance(value, int)
                and not isinstance(value, bool)
        ):
            return str(value)

        return None

    @staticmethod
    def _assignment_strategy_value(
            strategy: AssignmentStrategy | str,
    ) -> str:
        """获取实验固定分配策略文本.

        参数：
            strategy: 分配策略枚举或字符串

        返回：
            分配策略文本
        """
        return str(strategy).lower()

    @staticmethod
    def _is_effective(
            experiment: Experiment,
            now: datetime,
    ) -> bool:
        """判断实验当前是否在生效时间内.

        参数：
            experiment: 实验对象
            now: 当前时间

        返回：
            是否生效
        """
        current_time = to_utc(now)

        if experiment.effective_from is not None:
            effective_from = to_utc(experiment.effective_from)

            if effective_from > current_time:
                return False

        if experiment.effective_to is not None:
            effective_to = to_utc(experiment.effective_to)

            if effective_to <= current_time:
                return False

        return True
