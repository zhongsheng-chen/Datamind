# datamind/ab_test/analyzer.py

"""A/B 实验分析器

负责读取实验、实验分组和实验结果，并调用指标评估器生成实验分析结果。

核心功能：
  - VariantInfo: 实验分组信息
  - ABTestAnalysis: A/B 实验分析结果
  - ABTestAnalyzer: A/B 实验分析器

使用示例：
  from datamind.ab_test.analyzer import ABTestAnalyzer
  from datamind.ab_test.metrics import ABTestMetricEvaluator
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import (
      ExperimentRepository,
      OutcomeRepository,
      VariantRepository
  )

  async with UnitOfWork() as uow:
      analyzer = ABTestAnalyzer(
          experiment_repo=ExperimentRepository(uow.session),
          variant_repo=VariantRepository(uow.session),
          outcome_repo=OutcomeRepository(uow.session),
          metric_evaluator=ABTestMetricEvaluator()
      )

      analysis = await analyzer.analyze_experiment(
          experiment_id="exp_a1b2c3d4"
      )

      result = analysis.to_dict()
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from datamind.ab_test.metrics import ABTestMetricEvaluator, ExperimentMetrics
from datamind.db.models.outcomes import Outcome
from datamind.db.models.variants import Variant
from datamind.db.repositories.experiment import ExperimentRepository
from datamind.db.repositories.outcome import OutcomeRepository
from datamind.db.repositories.variant import VariantRepository


@dataclass(slots=True)
class VariantInfo:
    """实验分组信息

    属性：
        variant_id: 实验分组 ID
        experiment_id: 实验 ID
        name: 实验分组名称
        deployment_id: 部署 ID
        weight: 分组权重
        is_control: 是否为对照组
        status: 分组状态
        description: 分组说明
    """

    variant_id: str
    experiment_id: str
    name: str
    deployment_id: str
    weight: float
    is_control: bool
    status: str
    description: str | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


@dataclass(slots=True)
class ABTestAnalysis:
    """A/B 实验分析结果

    属性：
        experiment_id: 实验 ID
        model_id: 模型 ID
        name: 实验名称
        status: 实验状态
        baseline_variant_id: 基准分组 ID
        outcome_count: 实验结果记录数
        variants: 实验分组信息，key 为 variant_id
        metrics: 实验指标结果
        warnings: 分析提示信息
    """

    experiment_id: str
    model_id: str
    name: str | None
    status: str
    baseline_variant_id: str | None
    outcome_count: int
    variants: dict[str, VariantInfo]
    metrics: ExperimentMetrics
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "experiment_id": self.experiment_id,
            "model_id": self.model_id,
            "name": self.name,
            "status": self.status,
            "baseline_variant_id": self.baseline_variant_id,
            "outcome_count": self.outcome_count,
            "variants": {
                variant_id: variant.to_dict()
                for variant_id, variant in self.variants.items()
            },
            "metrics": self.metrics.to_dict(),
            "warnings": self.warnings,
        }


class ABTestAnalyzer:
    """A/B 实验分析器

    读取实验配置、实验分组和实验结果，
    并调用 ABTestMetricEvaluator 生成实验分析结果。
    """

    def __init__(
            self,
            *,
            experiment_repo: ExperimentRepository,
            variant_repo: VariantRepository,
            outcome_repo: OutcomeRepository,
            metric_evaluator: ABTestMetricEvaluator | None = None,
    ):
        """初始化 A/B 实验分析器

        参数：
            experiment_repo: 实验仓储
            variant_repo: 实验分组仓储
            outcome_repo: 实验结果仓储
            metric_evaluator: A/B 实验指标评估器（可选）
        """
        self.experiment_repo = experiment_repo
        self.variant_repo = variant_repo
        self.outcome_repo = outcome_repo
        self.metric_evaluator = metric_evaluator or ABTestMetricEvaluator()

    async def analyze_experiment(
            self,
            *,
            experiment_id: str,
            baseline_variant_id: str | None = None,
    ) -> ABTestAnalysis:
        """分析指定实验

        参数：
            experiment_id: 实验 ID
            baseline_variant_id: 基准分组 ID（可选）

        返回：
            A/B 实验分析结果

        异常：
            ValueError: 实验不存在、实验分组不存在或基准分组不存在
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        experiment = await self.experiment_repo.get_experiment(
            experiment_id=experiment_id,
        )

        if experiment is None:
            raise ValueError("实验不存在")

        variants = await self.variant_repo.list_variants(
            experiment_id=experiment_id,
        )

        if not variants:
            raise ValueError("实验没有分组")

        resolved_baseline_variant_id = await self._resolve_baseline_variant_id(
            experiment_id=experiment_id,
            variants=variants,
            baseline_variant_id=baseline_variant_id,
        )

        outcomes = await self._list_experiment_outcomes(
            experiment_id=experiment_id,
        )

        outcome_variant_ids = self._get_outcome_variant_ids(outcomes)

        metrics_baseline_variant_id = resolved_baseline_variant_id

        if (
                metrics_baseline_variant_id is not None
                and metrics_baseline_variant_id not in outcome_variant_ids
        ):
            metrics_baseline_variant_id = None

        metrics_result = self.metric_evaluator.calculate_experiment_metrics(
            experiment_id=experiment_id,
            outcomes=outcomes,
            baseline_variant_id=metrics_baseline_variant_id,
        )

        variant_map = self._build_variant_info_map(variants)

        warnings = self._build_warnings(
            variants=variants,
            outcomes=outcomes,
            baseline_variant_id=resolved_baseline_variant_id,
            metrics=metrics_result,
        )

        return ABTestAnalysis(
            experiment_id=self._as_str(experiment.experiment_id),
            model_id=self._as_str(experiment.model_id),
            name=self._as_optional_str(experiment.name),
            status=self._as_str(experiment.status),
            baseline_variant_id=resolved_baseline_variant_id,
            outcome_count=len(outcomes),
            variants=variant_map,
            metrics=metrics_result,
            warnings=warnings,
        )

    async def analyze_variant(
            self,
            *,
            variant_id: str,
    ) -> dict:
        """分析单个实验分组

        参数：
            variant_id: 实验分组 ID

        返回：
            单个实验分组分析结果

        异常：
            ValueError: 分组不存在
        """
        if not variant_id:
            raise ValueError("实验分组 ID 不能为空")

        variant = await self.variant_repo.get_variant(variant_id)

        if variant is None:
            raise ValueError("实验分组不存在")

        outcomes = await self._list_variant_outcomes(
            variant_id=variant_id,
        )

        metrics_map = self.metric_evaluator.calculate_variant_metrics(
            outcomes=outcomes,
        )

        variant_id_value = self._as_str(variant.variant_id)
        metrics_result = metrics_map.get(variant_id_value)

        return {
            "variant": self._build_variant_info(variant).to_dict(),
            "outcome_count": len(outcomes),
            "metrics": (
                metrics_result.to_dict()
                if metrics_result is not None
                else None
            ),
        }

    async def _resolve_baseline_variant_id(
            self,
            *,
            experiment_id: str,
            variants: list[Variant],
            baseline_variant_id: str | None,
    ) -> str | None:
        """解析基准分组 ID

        参数：
            experiment_id: 实验 ID
            variants: 实验分组列表
            baseline_variant_id: 用户指定的基准分组 ID

        返回：
            基准分组 ID，没有可用基准分组时返回 None

        异常：
            ValueError: 指定的基准分组不存在
        """
        variant_ids = {
            self._as_str(variant.variant_id)
            for variant in variants
        }

        if baseline_variant_id is not None:
            if baseline_variant_id not in variant_ids:
                raise ValueError("基准分组不存在")

            return baseline_variant_id

        control_variant = await self.variant_repo.get_control_variant(
            experiment_id=experiment_id,
        )

        if control_variant is not None:
            return self._as_str(control_variant.variant_id)

        return None

    async def _list_experiment_outcomes(
            self,
            *,
            experiment_id: str,
    ) -> list[Outcome]:
        """获取实验全部结果记录

        参数：
            experiment_id: 实验 ID

        返回：
            实验结果记录列表
        """
        return await self.outcome_repo.list_experiment_outcomes(
            experiment_id
        )

    async def _list_variant_outcomes(
            self,
            *,
            variant_id: str,
    ) -> list[Outcome]:
        """获取实验分组全部结果记录

        参数：
            variant_id: 实验分组 ID

        返回：
            实验结果记录列表
        """
        return await self.outcome_repo.list_variant_outcomes(
            variant_id
        )

    @classmethod
    def _build_variant_info_map(
            cls,
            variants: list[Variant],
    ) -> dict[str, VariantInfo]:
        """构造实验分组信息字典

        参数：
            variants: 实验分组列表

        返回：
            分组信息字典，key 为 variant_id
        """
        return {
            cls._as_str(variant.variant_id): cls._build_variant_info(variant)
            for variant in variants
        }

    @classmethod
    def _build_variant_info(
            cls,
            variant: Variant,
    ) -> VariantInfo:
        """构造实验分组信息

        参数：
            variant: 实验分组对象

        返回：
            实验分组信息
        """
        return VariantInfo(
            variant_id=cls._as_str(variant.variant_id),
            experiment_id=cls._as_str(variant.experiment_id),
            name=cls._as_str(variant.name),
            deployment_id=cls._as_str(variant.deployment_id),
            weight=cls._as_float(variant.weight),
            is_control=cls._as_bool(variant.is_control),
            status=cls._as_str(variant.status),
            description=cls._as_optional_str(variant.description),
        )

    @classmethod
    def _build_warnings(
            cls,
            *,
            variants: list[Variant],
            outcomes: list[Outcome],
            baseline_variant_id: str | None,
            metrics: ExperimentMetrics,
    ) -> list[str]:
        """构造分析提示信息

        参数：
            variants: 实验分组列表
            outcomes: 实验结果记录列表
            baseline_variant_id: 基准分组 ID
            metrics: 实验指标结果

        返回：
            提示信息列表
        """
        warnings: list[str] = []

        if not outcomes:
            warnings.append("实验暂无结果记录")

        if baseline_variant_id is None:
            warnings.append("未找到基准分组，未生成 lift 对比")
        elif baseline_variant_id not in metrics.variants:
            warnings.append(
                f"基准分组 {baseline_variant_id} 暂无结果记录，未生成 lift 对比"
            )

        variant_ids = {
            cls._as_str(variant.variant_id)
            for variant in variants
        }

        variant_ids_with_metrics = set(metrics.variants.keys())

        for variant in variants:
            variant_id = cls._as_str(variant.variant_id)

            if variant_id not in variant_ids_with_metrics:
                warnings.append(
                    f"实验分组 {variant_id} 暂无结果记录"
                )

        invalid_variant_count = sum(
            1
            for outcome in outcomes
            if not cls._is_valid_variant_id(
                getattr(outcome, "variant_id", None)
            )
        )

        if invalid_variant_count > 0:
            warnings.append(
                f"存在 {invalid_variant_count} 条结果记录缺少有效实验分组 ID"
            )

        outcome_variant_ids = cls._get_outcome_variant_ids(outcomes)
        unknown_variant_ids = outcome_variant_ids - variant_ids

        if unknown_variant_ids:
            unknown_variant_text = ", ".join(
                sorted(unknown_variant_ids)
            )

            warnings.append(
                f"存在未配置的实验分组结果：{unknown_variant_text}"
            )

        active_weight_sum = sum(
            cls._as_float(variant.weight)
            for variant in variants
            if cls._as_float(variant.weight) > 0
        )

        if abs(active_weight_sum - 1.0) > 1e-8:
            warnings.append("实验分组权重总和不等于 1")

        return warnings

    @classmethod
    def _get_outcome_variant_ids(
            cls,
            outcomes: list[Outcome],
    ) -> set[str]:
        """获取实验结果中的有效分组 ID

        参数：
            outcomes: 实验结果记录列表

        返回：
            实验分组 ID 集合
        """
        return {
            str(variant_id)
            for outcome in outcomes
            if cls._is_valid_variant_id(
                variant_id := getattr(outcome, "variant_id", None)
            )
        }

    @staticmethod
    def _is_valid_variant_id(value: Any) -> bool:
        """判断实验分组 ID 是否有效

        参数：
            value: 原始值

        返回：
            是否为有效实验分组 ID
        """
        return isinstance(value, str) and bool(value)

    @staticmethod
    def _as_str(value: Any) -> str:
        """转换为字符串

        参数：
            value: 原始值

        返回：
            字符串
        """
        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        """转换为可选字符串

        参数：
            value: 原始值

        返回：
            字符串；输入为 None 时返回 None
        """
        if value is None:
            return None

        return str(value)

    @staticmethod
    def _as_float(value: Any) -> float:
        """转换为浮点数

        参数：
            value: 原始值

        返回：
            浮点数，无法转换时返回 0
        """
        if value is None:
            return 0.0

        if isinstance(value, bool):
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _as_bool(value: Any) -> bool:
        """转换为布尔值

        参数：
            value: 原始值

        返回：
            布尔值
        """
        if isinstance(value, bool):
            return value

        return bool(value)
