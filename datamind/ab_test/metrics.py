"""A/B 实验指标评估.

根据实验结果记录计算 A/B 测试指标，用于实验效果评估和模型表现对比。

核心功能：
  - VariantMetrics: 实验分组指标
  - MetricComparison: 指标对比结果
  - ExperimentMetrics: 实验整体指标
  - ABTestMetricEvaluator: A/B 实验指标评估器

使用示例：
  from datamind.ab_test.metrics import ABTestMetricEvaluator

  evaluator = ABTestMetricEvaluator()

  metrics = evaluator.calculate_experiment_metrics(
      experiment_id="exp_0123456789abcdef",
      outcomes=outcomes,
      baseline_variant_id="var_control",
  )

  result = metrics.to_dict()
"""

from dataclasses import asdict, dataclass, field
import math
from typing import Any


@dataclass(slots=True)
class VariantMetrics:
    """实验分组指标.

    属性：
        experiment_id: 实验 ID
        variant_id: 实验分组 ID
        total_count: 样本总数
        approved_count: 审批通过数
        converted_count: 转化数
        defaulted_count: 违约数
        bad_count: 坏样本数
        amount_count: 有金额记录数
        total_amount: 总金额
        average_amount: 平均金额
        approval_rate: 审批通过率
        conversion_rate: 转化率
        default_rate: 违约率
        bad_rate: 坏样本率
    """

    experiment_id: str | None
    variant_id: str
    total_count: int = 0
    approved_count: int = 0
    converted_count: int = 0
    defaulted_count: int = 0
    bad_count: int = 0
    amount_count: int = 0
    total_amount: float = 0.0
    average_amount: float = 0.0
    approval_rate: float = 0.0
    conversion_rate: float = 0.0
    default_rate: float = 0.0
    bad_rate: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)


@dataclass(slots=True)
class MetricComparison:
    """指标对比结果.

    属性：
        metric: 指标名称
        baseline_variant_id: 基准分组 ID
        variant_id: 对比分组 ID
        baseline_value: 基准分组指标值
        variant_value: 对比分组指标值
        absolute_lift: 绝对提升，variant_value - baseline_value
        relative_lift: 相对提升，baseline_value 为 0 时返回 None
    """

    metric: str
    baseline_variant_id: str
    variant_id: str
    baseline_value: float
    variant_value: float
    absolute_lift: float
    relative_lift: float | None

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)


@dataclass(slots=True)
class ExperimentMetrics:
    """实验整体指标.

    属性：
        experiment_id: 实验 ID
        total_count: 实验样本总数
        baseline_variant_id: 基准分组 ID
        variants: 分组指标，key 为 variant_id
        comparisons: 分组对比结果，第一层 key 为 variant_id，第二层 key 为 metric
    """

    experiment_id: str
    total_count: int
    baseline_variant_id: str | None
    variants: dict[str, VariantMetrics]
    comparisons: dict[str, dict[str, MetricComparison]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "experiment_id": self.experiment_id,
            "total_count": self.total_count,
            "baseline_variant_id": self.baseline_variant_id,
            "variants": {
                variant_id: metrics.to_dict()
                for variant_id, metrics in self.variants.items()
            },
            "comparisons": {
                variant_id: {
                    metric: comparison.to_dict()
                    for metric, comparison in metric_map.items()
                }
                for variant_id, metric_map in self.comparisons.items()
            },
        }


class ABTestMetricEvaluator:
    """A/B 实验指标评估器.

    提供 A/B 实验分组指标、整体指标和 lift 对比的评估能力。

    说明：
      - total_count 使用 outcome 记录数
      - approval_rate = approved_count / total_count
      - conversion_rate = converted_count / total_count
      - default_rate = defaulted_count / total_count
      - bad_rate = bad_count / total_count
      - bad_count 会综合 defaulted、label、overdue_days 判断
    """

    def __init__(
        self,
        *,
        bad_label: str = "bad",
        overdue_bad_threshold: int = 30,
    ):
        """初始化 A/B 实验指标评估器.

        参数：
            bad_label: 坏样本标签，默认值为 bad
            overdue_bad_threshold: 坏样本逾期天数阈值，默认值为 30
        """
        self.bad_label = bad_label
        self.overdue_bad_threshold = overdue_bad_threshold

    def calculate_experiment_metrics(
        self,
        *,
        experiment_id: str,
        outcomes: list[Any],
        baseline_variant_id: str | None = None,
    ) -> ExperimentMetrics:
        """计算实验整体指标.

        参数：
            experiment_id: 实验 ID
            outcomes: 实验结果记录列表
            baseline_variant_id: 基准分组 ID（可选）

        返回：
            实验整体指标

        异常：
            ValueError: 实验 ID 为空，或 baseline_variant_id 不存在
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        experiment_outcomes = [
            item for item in outcomes
            if getattr(item, "experiment_id", None) == experiment_id
        ]

        variants = self.calculate_variant_metrics(
            outcomes=experiment_outcomes,
        )

        if baseline_variant_id is not None:
            if baseline_variant_id not in variants:
                raise ValueError("基准分组不存在")

        comparisons = self._compare_variants(
            variants=variants,
            baseline_variant_id=baseline_variant_id,
        )

        total_count = sum(
            metrics.total_count
            for metrics in variants.values()
        )

        return ExperimentMetrics(
            experiment_id=experiment_id,
            total_count=total_count,
            baseline_variant_id=baseline_variant_id,
            variants=variants,
            comparisons=comparisons,
        )

    def calculate_variant_metrics(
        self,
        *,
        outcomes: list[Any],
    ) -> dict[str, VariantMetrics]:
        """计算实验分组指标.

        参数：
            outcomes: 实验结果记录列表

        返回：
            分组指标字典，key 为 variant_id
        """
        grouped: dict[str, list[Any]] = {}

        for outcome in outcomes:
            variant_id = getattr(outcome, "variant_id", None)

            if not isinstance(variant_id, str) or not variant_id:
                continue

            grouped.setdefault(variant_id, []).append(outcome)

        result: dict[str, VariantMetrics] = {}

        for variant_id, items in grouped.items():
            result[variant_id] = self._calculate_single_variant_metrics(
                variant_id=variant_id,
                outcomes=items,
            )

        return result

    def _calculate_single_variant_metrics(
        self,
        *,
        variant_id: str,
        outcomes: list[Any],
    ) -> VariantMetrics:
        """计算单个实验分组指标.

        参数：
            variant_id: 实验分组 ID
            outcomes: 分组下的结果记录列表

        返回：
            实验分组指标
        """
        total_count = len(outcomes)
        experiment_id = self._first_experiment_id(outcomes)

        approved_count = 0
        converted_count = 0
        defaulted_count = 0
        bad_count = 0
        amount_count = 0
        total_amount = 0.0

        for outcome in outcomes:
            if getattr(outcome, "approved", None):
                approved_count += 1

            if getattr(outcome, "converted", None):
                converted_count += 1

            if getattr(outcome, "defaulted", None):
                defaulted_count += 1

            if self._is_bad_outcome(outcome):
                bad_count += 1

            amount = self._to_float(getattr(outcome, "amount", None))

            if amount is not None:
                amount_count += 1
                total_amount += amount

        return VariantMetrics(
            experiment_id=experiment_id,
            variant_id=variant_id,
            total_count=total_count,
            approved_count=approved_count,
            converted_count=converted_count,
            defaulted_count=defaulted_count,
            bad_count=bad_count,
            amount_count=amount_count,
            total_amount=total_amount,
            average_amount=self._safe_divide(total_amount, amount_count),
            approval_rate=self._safe_divide(approved_count, total_count),
            conversion_rate=self._safe_divide(converted_count, total_count),
            default_rate=self._safe_divide(defaulted_count, total_count),
            bad_rate=self._safe_divide(bad_count, total_count),
        )

    def _compare_variants(
        self,
        *,
        variants: dict[str, VariantMetrics],
        baseline_variant_id: str | None,
    ) -> dict[str, dict[str, MetricComparison]]:
        """计算各分组相对基准组的指标提升.

        参数：
            variants: 分组指标
            baseline_variant_id: 基准分组 ID

        返回：
            分组对比结果
        """
        if baseline_variant_id is None:
            return {}

        baseline = variants[baseline_variant_id]
        comparisons: dict[str, dict[str, MetricComparison]] = {}

        for variant_id, metrics in variants.items():
            if variant_id == baseline_variant_id:
                continue

            comparisons[variant_id] = {
                "approval_rate": self._compare_metric(
                    metric="approval_rate",
                    baseline_variant_id=baseline_variant_id,
                    variant_id=variant_id,
                    baseline_value=baseline.approval_rate,
                    variant_value=metrics.approval_rate,
                ),
                "conversion_rate": self._compare_metric(
                    metric="conversion_rate",
                    baseline_variant_id=baseline_variant_id,
                    variant_id=variant_id,
                    baseline_value=baseline.conversion_rate,
                    variant_value=metrics.conversion_rate,
                ),
                "default_rate": self._compare_metric(
                    metric="default_rate",
                    baseline_variant_id=baseline_variant_id,
                    variant_id=variant_id,
                    baseline_value=baseline.default_rate,
                    variant_value=metrics.default_rate,
                ),
                "bad_rate": self._compare_metric(
                    metric="bad_rate",
                    baseline_variant_id=baseline_variant_id,
                    variant_id=variant_id,
                    baseline_value=baseline.bad_rate,
                    variant_value=metrics.bad_rate,
                ),
                "average_amount": self._compare_metric(
                    metric="average_amount",
                    baseline_variant_id=baseline_variant_id,
                    variant_id=variant_id,
                    baseline_value=baseline.average_amount,
                    variant_value=metrics.average_amount,
                ),
            }

        return comparisons

    @staticmethod
    def _compare_metric(
        *,
        metric: str,
        baseline_variant_id: str,
        variant_id: str,
        baseline_value: float,
        variant_value: float,
    ) -> MetricComparison:
        """计算单个指标对比结果.

        参数：
            metric: 指标名称
            baseline_variant_id: 基准分组 ID
            variant_id: 对比分组 ID
            baseline_value: 基准分组指标值
            variant_value: 对比分组指标值

        返回：
            指标对比结果
        """
        absolute_lift = variant_value - baseline_value

        if baseline_value == 0:
            relative_lift = None
        else:
            relative_lift = absolute_lift / baseline_value

        return MetricComparison(
            metric=metric,
            baseline_variant_id=baseline_variant_id,
            variant_id=variant_id,
            baseline_value=baseline_value,
            variant_value=variant_value,
            absolute_lift=absolute_lift,
            relative_lift=relative_lift,
        )

    def _is_bad_outcome(self, outcome: Any) -> bool:
        """判断是否为坏样本.

        参数：
            outcome: 实验结果记录

        返回：
            是否为坏样本
        """
        if getattr(outcome, "defaulted", None):
            return True

        label = getattr(outcome, "label", None)

        if isinstance(label, str) and label.lower() == self.bad_label.lower():
            return True

        overdue_days = self._to_int(getattr(outcome, "overdue_days", None))

        if overdue_days is not None:
            return overdue_days > self.overdue_bad_threshold

        return False

    @staticmethod
    def _first_experiment_id(outcomes: list[Any]) -> str | None:
        """获取第一条结果记录的实验 ID.

        参数：
            outcomes: 实验结果记录列表

        返回：
            实验 ID，不存在时返回 None
        """
        if not outcomes:
            return None

        experiment_id = getattr(outcomes[0], "experiment_id", None)

        if isinstance(experiment_id, str) and experiment_id:
            return experiment_id

        return None

    @staticmethod
    def _safe_divide(
        numerator: float | int,
        denominator: float | int,
    ) -> float:
        """安全除法.

        参数：
            numerator: 分子
            denominator: 分母

        返回：
            除法结果，分母为 0 时返回 0
        """
        if denominator == 0:
            return 0.0

        return float(numerator) / float(denominator)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """转换为浮点数.

        参数：
            value: 原始值

        返回：
            浮点数；无法转换时返回 None
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            result = float(value)
            return result if math.isfinite(result) else None

        if isinstance(value, str) and value.strip():
            try:
                result = float(value)
                return result if math.isfinite(result) else None
            except ValueError:
                return None

        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        """转换为整数.

        参数：
            value: 原始值

        返回：
            整数；无法转换时返回 None
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None

        return None
