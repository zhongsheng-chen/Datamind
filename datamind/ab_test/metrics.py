"""A/B 实验指标评估.

根据请求决策和主执行记录计算流量、运行及预测分布指标。

核心功能：
  - VariantMetrics: 实验分组指标
  - MetricComparison: 指标对比结果
  - ExperimentMetrics: 实验整体指标
  - ABTestMetricEvaluator: A/B 实验指标评估器
"""

from collections import Counter
from dataclasses import asdict, dataclass, field
import math
from typing import Any


@dataclass(slots=True)
class VariantMetrics:
    """实验分组指标.

    属性：
        total_count: 决策记录数，重复主体的请求分别计数
        subject_count: 不同主体类型与标识的组合数
        assignment_count: 不同实验分配记录数
        traffic_ratio: 当前分析范围内的决策占比
        execution_count: 主执行记录数
        completed_count: 已结束的主执行记录数
        success_rate: 成功主执行数除以已结束主执行数
        average_latency_ms: 已结束主执行的平均有效耗时
        average_probability: 成功主执行的平均有效预测概率
        average_score: 成功主执行的平均有效评分
        prediction_counts: 成功主执行的分类标签分布
    """

    experiment_id: str | None
    variant_id: str
    total_count: int = 0
    subject_count: int = 0
    assignment_count: int = 0
    traffic_ratio: float = 0.0
    execution_count: int = 0
    completed_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    timeout_count: int = 0
    cancelled_count: int = 0
    queued_count: int = 0
    running_count: int = 0
    success_rate: float | None = None
    latency_count: int = 0
    average_latency_ms: float | None = None
    probability_count: int = 0
    average_probability: float | None = None
    minimum_probability: float | None = None
    maximum_probability: float | None = None
    score_count: int = 0
    average_score: float | None = None
    minimum_score: float | None = None
    maximum_score: float | None = None
    decision_counts: dict[str, int] = field(default_factory=dict)
    prediction_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)


@dataclass(slots=True)
class MetricComparison:
    """分组指标差异，正值表示实验组的数值较高."""

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
    """实验整体指标，按决策所属分组统计."""

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
            "variants": {key: value.to_dict() for key, value in self.variants.items()},
            "comparisons": {
                key: {name: value.to_dict() for name, value in values.items()}
                for key, values in self.comparisons.items()
            },
        }


class ABTestMetricEvaluator:
    """使用决策与主执行记录评估实验运行情况."""

    def calculate_experiment_metrics(
            self,
            *,
            experiment_id: str,
            decisions: list[Any],
            executions: list[Any],
            baseline_variant_id: str | None = None,
    ) -> ExperimentMetrics:
        """计算实验指标.

        参数：
            experiment_id: 实验 ID
            decisions: 原始请求决策记录
            executions: 对应的执行记录，影子执行不参与指标计算
            baseline_variant_id: 基准分组 ID

        返回：
            实验指标及有有效样本的分组差异
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        selected = [item for item in decisions if item.experiment_id == experiment_id]
        variants = self.calculate_variant_metrics(decisions=selected, executions=executions)
        if baseline_variant_id is not None and baseline_variant_id not in variants:
            raise ValueError("基准分组没有决策记录")

        comparisons = {}
        if baseline_variant_id is not None:
            baseline = variants[baseline_variant_id]
            for key, metrics in variants.items():
                if key == baseline_variant_id:
                    continue
                values = {}
                for name in (
                        "success_rate", "average_latency_ms",
                        "average_probability", "average_score",
                ):
                    base_value = getattr(baseline, name)
                    value = getattr(metrics, name)
                    if base_value is None or value is None:
                        continue
                    values[name] = MetricComparison(
                        metric=name,
                        baseline_variant_id=baseline_variant_id,
                        variant_id=key,
                        baseline_value=base_value,
                        variant_value=value,
                        absolute_lift=value - base_value,
                        relative_lift=(value - base_value) / base_value if base_value else None,
                    )
                comparisons[key] = values

        return ExperimentMetrics(
            experiment_id=experiment_id,
            total_count=len(selected),
            baseline_variant_id=baseline_variant_id,
            variants=variants,
            comparisons=comparisons,
        )

    def calculate_variant_metrics(
            self,
            *,
            decisions: list[Any],
            executions: list[Any],
    ) -> dict[str, VariantMetrics]:
        """按决策分组计算指标，排除影子与无关联执行."""
        grouped: dict[str, list[Any]] = {}
        primary: dict[str, list[Any]] = {}
        for item in executions:
            if item.execution_type == "primary":
                primary.setdefault(item.decision_id, []).append(item)
        for item in decisions:
            if isinstance(item.variant_id, str) and item.variant_id:
                grouped.setdefault(item.variant_id, []).append(item)

        result = {}
        for variant_id, items in grouped.items():
            runs = [run for item in items for run in primary.get(item.decision_id, [])]
            statuses = Counter(run.status for run in runs)
            finished = [run for run in runs if run.status in ("success", "failed", "timeout", "cancelled")]
            successful = [run for run in runs if run.status == "success"]
            latency = self._numbers(finished, "latency_ms")
            probability = self._numbers(successful, "probability")
            scores = self._numbers(successful, "score")
            labels = Counter()
            for run in successful:
                prediction = run.prediction
                if isinstance(prediction, dict):
                    label = prediction.get("label")
                    if isinstance(label, (str, int, float, bool)):
                        labels[str(label)] += 1
            result[variant_id] = VariantMetrics(
                experiment_id=items[0].experiment_id,
                variant_id=variant_id,
                total_count=len(items),
                subject_count=len({(item.subject_type, item.subject_key) for item in items if item.subject_key is not None}),
                assignment_count=len({item.assignment_id for item in items if item.assignment_id is not None}),
                traffic_ratio=len(items) / len(decisions) if decisions else 0.0,
                execution_count=len(runs),
                completed_count=len(finished),
                success_count=statuses["success"],
                failed_count=statuses["failed"],
                timeout_count=statuses["timeout"],
                cancelled_count=statuses["cancelled"],
                queued_count=statuses["queued"],
                running_count=statuses["running"],
                success_rate=statuses["success"] / len(finished) if finished else None,
                latency_count=len(latency),
                average_latency_ms=self._mean(latency),
                probability_count=len(probability),
                average_probability=self._mean(probability),
                minimum_probability=min(probability) if probability else None,
                maximum_probability=max(probability) if probability else None,
                score_count=len(scores),
                average_score=self._mean(scores),
                minimum_score=min(scores) if scores else None,
                maximum_score=max(scores) if scores else None,
                decision_counts=dict(Counter(item.decision for item in items if item.decision is not None)),
                prediction_counts=dict(labels),
            )
        return result

    @staticmethod
    def _numbers(records: list[Any], field_name: str) -> list[float]:
        """提取有效数值，忽略缺失值、布尔值和非有限数值."""
        values = []
        for record in records:
            value = getattr(record, field_name, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                values.append(float(value))
        return values

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        """计算平均值，无有效样本时返回 None."""
        return sum(values) / len(values) if values else None
