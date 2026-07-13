# tests/core/scoring/test_exports.py

"""评分包公共导出测试

验证评分包公开 API 的完整性和可访问性。

核心功能：
  - test_scoring_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.core.scoring as scoring


EXPECTED_EXPORTS = {
    "BaseScorer",
    "LRContrib",
    "Scorer",
    "ScoreTransformer",
}


def test_scoring_exports_expected_public_api() -> None:
    """测试评分包公开完整且准确的 API"""
    assert set(scoring.__all__) == EXPECTED_EXPORTS
    assert len(scoring.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in scoring.__all__:
        assert hasattr(scoring, name), name
