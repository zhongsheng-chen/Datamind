# tests/core/scoring/test_base.py

"""评分组件基类测试

验证评分组件基类的能力声明、能力查询、组合能力判断、
能力要求和参数类型校验。

核心功能：
  - 验证默认能力
  - 验证单个和组合能力
  - 验证 NONE 能力
  - 验证能力要求
  - 验证不支持能力的异常
  - 验证参数类型
"""

from typing import Any

import pytest

from datamind.core.capability import (
    ModelCapability,
    ScorecardCapability,
)
from datamind.core.scoring.base import BaseScorer


class EmptyScorer(
        BaseScorer
):
    """无评分能力测试组件"""


class TotalScoreScorer(
        BaseScorer
):
    """总评分测试组件"""

    SUPPORTED_CAPABILITIES = (
        ScorecardCapability.SCORECARD_TOTAL_SCORE
    )


class CombinedScorer(
        BaseScorer
):
    """组合评分能力测试组件"""

    SUPPORTED_CAPABILITIES = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )


def test_default_capabilities_are_none(
) -> None:
    """测试基类默认不声明评分能力"""
    scorer = EmptyScorer()

    assert (
        scorer.capabilities
        == ScorecardCapability.NONE
    )

    assert (
        scorer.get_capabilities()
        == ScorecardCapability.NONE
    )


def test_capabilities_return_declared_class_value(
) -> None:
    """测试返回类声明的评分能力"""
    scorer = CombinedScorer()

    expected = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert scorer.capabilities == expected
    assert scorer.get_capabilities() == expected


def test_capability_declarations_are_independent(
) -> None:
    """测试不同评分组件的能力声明互不影响"""
    empty = EmptyScorer()
    total = TotalScoreScorer()
    combined = CombinedScorer()

    assert (
        empty.get_capabilities()
        == ScorecardCapability.NONE
    )

    assert (
        total.get_capabilities()
        == ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert (
        combined.get_capabilities()
        == (
            ScorecardCapability.SCORECARD_FEATURE_SCORE
            | ScorecardCapability.SCORECARD_TOTAL_SCORE
        )
    )


@pytest.mark.parametrize(
    "capability",
    [
        ScorecardCapability.SCORECARD_FEATURE_SCORE,
        ScorecardCapability.SCORECARD_TOTAL_SCORE,
    ],
)
def test_has_capability_returns_true_for_supported_capability(
        capability: ScorecardCapability,
) -> None:
    """测试已支持的单个能力返回 True"""
    scorer = CombinedScorer()

    assert scorer.has_capability(
        capability
    )


def test_has_capability_returns_false_for_missing_capability(
) -> None:
    """测试未支持的单个能力返回 False"""
    scorer = CombinedScorer()

    assert not scorer.has_capability(
        ScorecardCapability.SCORECARD_LOGIT
    )


def test_has_capability_requires_all_combined_capabilities(
) -> None:
    """测试组合能力必须全部具备"""
    scorer = CombinedScorer()

    supported = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    partially_supported = (
        ScorecardCapability.SCORECARD_LOGIT
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert scorer.has_capability(
        supported
    )

    assert not scorer.has_capability(
        partially_supported
    )


@pytest.mark.parametrize(
    "scorer",
    [
        EmptyScorer(),
        TotalScoreScorer(),
        CombinedScorer(),
    ],
)
def test_none_capability_is_always_satisfied(
        scorer: BaseScorer,
) -> None:
    """测试 NONE 不要求实际能力"""
    assert scorer.has_capability(
        ScorecardCapability.NONE
    )

    scorer.require_capability(
        ScorecardCapability.NONE
    )


def test_require_capability_returns_none_when_supported(
) -> None:
    """测试已支持能力校验成功"""
    scorer = CombinedScorer()

    required = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    scorer.require_capability(
        required
    )


def test_require_capability_reports_single_missing_capability(
) -> None:
    """测试单个未支持能力的异常消息"""
    scorer = TotalScoreScorer()

    with pytest.raises(
            NotImplementedError,
            match=(
                "^TotalScoreScorer 不支持能力: "
                "SCORECARD_FEATURE_SCORE$"
            ),
    ):
        scorer.require_capability(
            ScorecardCapability.SCORECARD_FEATURE_SCORE
        )


def test_require_capability_reports_requested_combination(
) -> None:
    """测试组合能力校验失败时列出所需能力"""
    scorer = TotalScoreScorer()

    required = (
        ScorecardCapability.SCORECARD_LOGIT
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    with pytest.raises(
            NotImplementedError,
            match=(
                "^TotalScoreScorer 不支持能力: "
                "SCORECARD_LOGIT, "
                "SCORECARD_TOTAL_SCORE$"
            ),
    ):
        scorer.require_capability(
            required
        )


def test_empty_scorer_reports_runtime_class_name(
) -> None:
    """测试异常消息包含实际评分组件名称"""
    scorer = EmptyScorer()

    with pytest.raises(
            NotImplementedError,
            match=(
                "^EmptyScorer 不支持能力: "
                "SCORECARD_TOTAL_SCORE$"
            ),
    ):
        scorer.require_capability(
            ScorecardCapability.SCORECARD_TOTAL_SCORE
        )


@pytest.mark.parametrize(
    "invalid_capability",
    [
        "SCORECARD_TOTAL_SCORE",
        1,
        ModelCapability.PREDICT_PROBA,
        None,
    ],
)
def test_has_capability_rejects_invalid_type(
        invalid_capability: Any,
) -> None:
    """测试能力查询拒绝非评分能力枚举"""
    scorer = CombinedScorer()

    with pytest.raises(
            TypeError,
            match=(
                "^capability 必须是 "
                "ScorecardCapability 枚举$"
            ),
    ):
        scorer.has_capability(
            invalid_capability
        )


@pytest.mark.parametrize(
    "invalid_capability",
    [
        "SCORECARD_TOTAL_SCORE",
        1,
        ModelCapability.PREDICT_PROBA,
        None,
    ],
)
def test_require_capability_rejects_invalid_type(
        invalid_capability: Any,
) -> None:
    """测试能力要求拒绝非评分能力枚举"""
    scorer = CombinedScorer()

    with pytest.raises(
            TypeError,
            match=(
                "^capability 必须是 "
                "ScorecardCapability 枚举$"
            ),
    ):
        scorer.require_capability(
            invalid_capability
        )
