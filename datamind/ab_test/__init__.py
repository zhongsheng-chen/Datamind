# datamind/ab_test/__init__.py

"""A/B 实验组件

提供实验分配、实验执行、指标评估和实验分析能力。

核心功能：
  - StableHashAssigner: 稳定哈希分配器
  - AssignmentResult: 实验分配结果
  - ABTestEngine: A/B 实验执行引擎
  - ABTestMetricEvaluator: A/B 实验指标评估器
  - ABTestAnalyzer: A/B 实验分析器
"""

from datamind.ab_test.assignment import AssignmentResult, StableHashAssigner
from datamind.ab_test.engine import ABTestEngine, ABTestResult
from datamind.ab_test.metrics import (
    ABTestMetricEvaluator,
    ExperimentMetrics,
    MetricComparison,
    VariantMetrics,
)
from datamind.ab_test.analyzer import ABTestAnalyzer, ABTestAnalysis, VariantInfo

__all__ = [
    "AssignmentResult",
    "StableHashAssigner",
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