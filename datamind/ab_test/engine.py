# datamind/ab_test/engine.py

"""A/B 实验执行引擎

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
          model_id="mdl_a1b2c3d4",
          subject_key="customer_10001",
          subject_type="customer"
      )

      if assignment is not None:
          deployment_id = assignment.deployment_id
          variant_id = assignment.variant_id

  async with UnitOfWork() as uow:
      engine = ABTestEngine(
          experiment_repo=ExperimentRepository(uow.session),
          variant_repo=VariantRepository(uow.session),
          assignment_repo=AssignmentRepository(uow.session)
      )

      assignment = await engine.assign(
          model_id="mdl_a1b2c3d4",
          payload={
              "customer_id": "customer_10001",
              "age": 35,
          },
          subject_type="customer"
      )
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from datamind.ab_test.assignment import AssignmentResult, StableHashAssigner
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
    """A/B 实验命中结果

    属性：
        experiment_id: 实验 ID
        variant_id: 实验分组 ID
        deployment_id: 命中的部署 ID
        assignment_id: 实验固定分配 ID
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
    """A/B 实验执行引擎

    根据模型 ID 查询运行中的实验，
    再根据 subject_key 判断是否进入实验，并稳定分配到实验分组。
    """

    def __init__(
        self,
        *,
        experiment_repo: ExperimentRepository,
        variant_repo: VariantRepository,
        assignment_repo: AssignmentRepository,
        assigner: StableHashAssigner | None = None,
    ):
        """初始化 A/B 实验执行引擎

        参数：
            experiment_repo: 实验仓储
            variant_repo: 实验分组仓储
            assignment_repo: 实验分配仓储
            assigner: 稳定哈希分配器（可选）
        """
        self.experiment_repo = experiment_repo
        self.variant_repo = variant_repo
        self.assignment_repo = assignment_repo
        self.assigner = assigner or StableHashAssigner()

    async def assign(
        self,
        *,
        model_id: str,
        subject_key: str | None = None,
        subject_type: str | None = None,
        payload: dict | None = None,
        now: datetime | None = None,
        flush: bool = False,
    ) -> ABTestResult | None:
        """分配 A/B 实验分组

        参数：
            model_id: 模型 ID
            subject_key: 分桶主体标识，例如客户号、订单号、申请单号。
                如果传入该参数，则优先使用该值。
            subject_type: 分桶主体类型（可选）
            payload: 请求负载。未传 subject_key 时，会根据实验配置中的 bucket_key
                从 payload 中提取分桶主体标识。
            now: 当前时间（可选）
            flush: 是否立即 flush 到数据库，默认 False

        返回：
            A/B 实验命中结果；如果没有命中实验，返回 None

        异常：
            ValueError: 参数或实验配置非法
        """
        if not model_id:
            raise ValueError("模型 ID 不能为空")

        if subject_key is None and payload is None:
            raise ValueError("分桶主体不能为空")

        current_time = to_utc(now or datetime.now(timezone.utc))

        experiments = await self.experiment_repo.list_running_experiments(
            model_id=model_id,
        )

        for experiment in experiments:
            if not self._is_effective(experiment, current_time):
                continue

            config = self._get_config(experiment)

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

            traffic_ratio = self._get_traffic_ratio(experiment)

            assignment_result = self.assigner.assign(
                experiment_id=experiment.experiment_id,
                subject_key=actual_subject_key,
                traffic_ratio=traffic_ratio,
                variants=variants,
            )

            if assignment_result is None:
                continue

            assignment_context = dict(assignment_result.context)
            assignment_context.update(
                {
                    "bucket_key": config.get("bucket_key"),
                }
            )

            assignment = self.assignment_repo.create_assignment(
                assignment_id=generate_random_id(
                    prefix="asn"
                ),
                experiment_id=experiment.experiment_id,
                variant_id=assignment_result.variant.variant_id,
                subject_key=actual_subject_key,
                subject_type=subject_type,
                strategy=AssignmentStrategy.HASH,
                bucket=assignment_result.bucket,
                weight=float(assignment_result.variant.weight),
                context=assignment_context,
                assigned_at=current_time,
            )

            if flush:
                await self.assignment_repo.flush()

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
        """根据已有固定分配构造实验命中结果

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

        if variant.status != ExperimentVariantStatus.ACTIVE:
            return None

        context = dict(assignment.context or {})
        context.update(
            {
                "source": "existing_assignment",
                "experiment_id": experiment.experiment_id,
                "variant_id": variant.variant_id,
                "variant_name": variant.name,
                "deployment_id": variant.deployment_id,
                "assignment_id": assignment.assignment_id,
                "subject_key": assignment.subject_key,
                "subject_type": subject_type or assignment.subject_type,
                "bucket": assignment.bucket,
                "strategy": AssignmentStrategy.HASH,
            }
        )

        return ABTestResult(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            deployment_id=variant.deployment_id,
            assignment_id=assignment.assignment_id,
            subject_key=assignment.subject_key,
            subject_type=subject_type or assignment.subject_type,
            source=DecisionStrategy.EXPERIMENT,
            strategy=AssignmentStrategy.HASH,
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
        """根据新分配结果构造实验命中结果

        参数：
            experiment: 实验对象
            assignment: 实验分配对象
            assignment_result: 稳定哈希分配结果
            subject_type: 分桶主体类型（可选）

        返回：
            A/B 实验命中结果
        """
        variant = assignment_result.variant

        context = dict(assignment.context or assignment_result.context)
        context.update(
            {
                "source": "new_assignment",
                "experiment_id": experiment.experiment_id,
                "variant_id": variant.variant_id,
                "variant_name": variant.name,
                "deployment_id": variant.deployment_id,
                "assignment_id": assignment.assignment_id,
                "subject_key": assignment.subject_key,
                "subject_type": subject_type,
                "bucket": assignment_result.bucket,
                "strategy": AssignmentStrategy.HASH,
            }
        )

        return ABTestResult(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            deployment_id=variant.deployment_id,
            assignment_id=assignment.assignment_id,
            subject_key=assignment.subject_key,
            subject_type=subject_type,
            source=DecisionStrategy.EXPERIMENT,
            strategy=AssignmentStrategy.HASH,
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
        """获取实验曝光比例

        参数：
            experiment: 实验对象

        返回：
            实验曝光比例，取值范围为 (0, 1]

        异常：
            ValueError: 实验配置非法
        """
        config = cls._get_config(experiment)

        traffic_ratio = float(config.get("traffic_ratio", 1.0))

        if traffic_ratio <= 0:
            raise ValueError("实验曝光比例必须大于 0")

        if traffic_ratio > 1:
            raise ValueError("实验曝光比例不能大于 1")

        return traffic_ratio

    @staticmethod
    def _get_config(experiment: Experiment) -> dict:
        """获取实验配置

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
    def _resolve_subject_key(
        *,
        subject_key: str | None,
        payload: dict | None,
        bucket_key: str | None,
    ) -> str | None:
        """解析分桶主体标识

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

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _is_effective(
        experiment: Experiment,
        now: datetime,
    ) -> bool:
        """判断实验当前是否在生效时间内

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