# datamind/ab_test/__init__.py

"""A/B 实验组件

提供实验分配、实验执行、指标评估和实验分析能力。

核心功能：
  - AssignmentResult: 实验分配结果
  - StableHashAssigner: 稳定 Hash 分配器
  - ManualAssigner: 手工指定分配器
  - ExperimentAssigner: 实验分配器
  - ABTestEngine: A/B 实验执行引擎
  - ABTestMetricEvaluator: A/B 实验指标评估器
  - ABTestAnalyzer: A/B 实验分析器

使用示例：
  from datamind.ab_test import StableHashAssigner

  result = StableHashAssigner().assign(
      experiment_id="exp_0123456789abcdef",
      subject_key="customer_10001",
      traffic_ratio=1.0,
      variants=variants,
  )
"""

from datamind.ab_test.analyzer import ABTestAnalysis, ABTestAnalyzer, VariantInfo
from datamind.ab_test.assignment import (
    AssignmentResult,
    ExperimentAssigner,
    ManualAssigner,
    StableHashAssigner,
)
from datamind.ab_test.engine import ABTestEngine, ABTestResult
from datamind.ab_test.metrics import (
    ABTestMetricEvaluator,
    ExperimentMetrics,
    MetricComparison,
    VariantMetrics,
)

__all__ = [
    "AssignmentResult",
    "StableHashAssigner",
    "ManualAssigner",
    "ExperimentAssigner",
    "ABTestEngine",
    "ABTestResult",
    "ABTestMetricEvaluator",
    "ExperimentMetrics",
    "MetricComparison",
    "VariantMetrics",
    "ABTestAnalyzer",
    "ABTestAnalysis",
    "VariantInfo",
]
