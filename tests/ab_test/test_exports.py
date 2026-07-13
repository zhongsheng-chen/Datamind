# tests/ab_test/test_exports.py

"""A/B 实验包公共导出测试

验证 A/B 实验包公开 API 的完整性和可访问性。

核心功能：
  - test_ab_test_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.ab_test as ab_test


EXPECTED_EXPORTS = {
    "ABTestAnalysis",
    "ABTestAnalyzer",
    "ABTestEngine",
    "ABTestMetricEvaluator",
    "ABTestResult",
    "AssignmentResult",
    "ExperimentAssigner",
    "ExperimentMetrics",
    "ManualAssigner",
    "MetricComparison",
    "StableHashAssigner",
    "VariantInfo",
    "VariantMetrics",
}


def test_ab_test_exports_expected_public_api() -> None:
    """测试 A/B 实验包公开完整且准确的 API"""
    assert set(ab_test.__all__) == EXPECTED_EXPORTS
    assert len(ab_test.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in ab_test.__all__:
        assert hasattr(ab_test, name), name
