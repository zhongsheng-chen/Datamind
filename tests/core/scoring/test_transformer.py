# tests/core/scoring/test_transformer.py

"""评分转换器测试

验证违约概率、Logit 和评分之间的转换公式、双向转换、
评分上下限和非法数值校验。

核心功能：
  - 验证评分因子和评分偏移
  - 验证违约概率与 Logit 转换
  - 验证 Logit 与评分转换
  - 验证评分与违约概率转换
  - 验证基准分和 PDO 关系
  - 验证评分上下限
  - 验证非法数值统一抛出 ValueError
"""

import math
from typing import Any

import pytest

from datamind.config.scorecard import ScorecardConfig
from datamind.core.scoring.transformer import ScoreTransformer


@pytest.fixture
def config(
) -> ScorecardConfig:
    """提供评分配置"""
    return ScorecardConfig(
        base_score=600.0,
        base_odds=50.0,
        pdo=20.0,
        min_score=0.0,
        max_score=1000.0,
    )


@pytest.fixture
def transformer(
        config: ScorecardConfig,
) -> ScoreTransformer:
    """提供评分转换器"""
    return ScoreTransformer(
        config=config
    )


def test_init_calculates_factor_and_offset(
        config: ScorecardConfig,
        transformer: ScoreTransformer,
) -> None:
    """测试评分因子和评分偏移"""
    expected_factor = (
        config.pdo
        / math.log(2)
    )

    expected_offset = (
        config.base_score
        - expected_factor
        * math.log(
            config.base_odds
        )
    )

    assert transformer.config is config

    assert transformer.factor == pytest.approx(
        expected_factor
    )

    assert transformer.offset == pytest.approx(
        expected_offset
    )


def test_base_odds_probability_maps_to_base_score(
        config: ScorecardConfig,
        transformer: ScoreTransformer,
) -> None:
    """测试基准好坏比对应基准分"""
    probability = (
        1.0
        / (
            1.0
            + config.base_odds
        )
    )

    result = transformer.probability_to_score(
        probability
    )

    assert result == pytest.approx(
        config.base_score
    )


def test_double_odds_increases_score_by_pdo(
        config: ScorecardConfig,
        transformer: ScoreTransformer,
) -> None:
    """测试好坏比翻倍时评分增加一个 PDO"""
    doubled_odds = (
        config.base_odds
        * 2.0
    )

    probability = (
        1.0
        / (
            1.0
            + doubled_odds
        )
    )

    result = transformer.probability_to_score(
        probability
    )

    assert result == pytest.approx(
        config.base_score
        + config.pdo
    )


@pytest.mark.parametrize(
    (
        "probability",
        "expected",
    ),
    [
        (
            0.5,
            0.0,
        ),
        (
            0.75,
            math.log(3.0),
        ),
        (
            0.25,
            -math.log(3.0),
        ),
    ],
)
def test_probability_to_logit(
        probability: float,
        expected: float,
) -> None:
    """测试违约概率转 Logit"""
    result = (
        ScoreTransformer.probability_to_logit(
            probability
        )
    )

    assert result == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    (
        "logit",
        "expected",
    ),
    [
        (
            0.0,
            0.5,
        ),
        (
            math.log(3.0),
            0.75,
        ),
        (
            -math.log(3.0),
            0.25,
        ),
    ],
)
def test_logit_to_probability(
        logit: float,
        expected: float,
) -> None:
    """测试 Logit 转违约概率"""
    result = (
        ScoreTransformer.logit_to_probability(
            logit
        )
    )

    assert result == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    "probability",
    [
        0.01,
        0.1,
        0.25,
        0.5,
        0.75,
        0.9,
        0.99,
    ],
)
def test_probability_and_logit_round_trip(
        probability: float,
) -> None:
    """测试违约概率与 Logit 双向转换"""
    logit = (
        ScoreTransformer.probability_to_logit(
            probability
        )
    )

    restored = (
        ScoreTransformer.logit_to_probability(
            logit
        )
    )

    assert restored == pytest.approx(
        probability
    )


@pytest.mark.parametrize(
    (
        "logit",
        "expected",
    ),
    [
        (
            1000.0,
            1.0,
        ),
        (
            -1000.0,
            0.0,
        ),
    ],
)
def test_logit_to_probability_is_stable_for_extreme_values(
        logit: float,
        expected: float,
) -> None:
    """测试极端 Logit 的数值稳定性"""
    result = (
        ScoreTransformer.logit_to_probability(
            logit
        )
    )

    assert result == expected


def test_logit_to_score_uses_score_formula(
        transformer: ScoreTransformer,
) -> None:
    """测试 Logit 转评分公式"""
    logit = 1.25

    expected = (
        transformer.offset
        - transformer.factor * logit
    )

    result = transformer.logit_to_score(
        logit
    )

    assert result == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    "logit",
    [
        -5.0,
        -1.0,
        0.0,
        1.0,
        5.0,
    ],
)
def test_logit_and_score_round_trip(
        logit: float,
        transformer: ScoreTransformer,
) -> None:
    """测试 Logit 与评分双向转换"""
    score = transformer.logit_to_score(
        logit
    )

    restored = transformer.score_to_logit(
        score
    )

    assert restored == pytest.approx(
        logit
    )


@pytest.mark.parametrize(
    "probability",
    [
        0.05,
        0.1,
        0.25,
        0.5,
        0.75,
        0.9,
        0.95,
    ],
)
def test_probability_and_score_round_trip(
        probability: float,
        transformer: ScoreTransformer,
) -> None:
    """测试违约概率与评分双向转换"""
    score = transformer.probability_to_score(
        probability
    )

    restored = transformer.score_to_probability(
        score
    )

    assert restored == pytest.approx(
        probability
    )


def test_score_to_probability_matches_composed_conversion(
        transformer: ScoreTransformer,
) -> None:
    """测试评分转概率等于评分转 Logit 再转概率"""
    score = 650.0

    expected = (
        transformer.logit_to_probability(
            transformer.score_to_logit(
                score
            )
        )
    )

    result = transformer.score_to_probability(
        score
    )

    assert result == pytest.approx(
        expected
    )


def test_logit_to_score_clamps_to_score_range(
        config: ScorecardConfig,
        transformer: ScoreTransformer,
) -> None:
    """测试 Logit 转评分应用上下限"""
    minimum = transformer.logit_to_score(
        1000.0
    )

    maximum = transformer.logit_to_score(
        -1000.0
    )

    assert minimum == config.min_score
    assert maximum == config.max_score


def test_probability_to_score_clamps_to_score_range(
        config: ScorecardConfig,
        transformer: ScoreTransformer,
) -> None:
    """测试违约概率转评分应用上下限"""
    minimum = transformer.probability_to_score(
        1.0 - 1e-15
    )

    maximum = transformer.probability_to_score(
        1e-15
    )

    assert minimum == config.min_score
    assert maximum == config.max_score


@pytest.mark.parametrize(
    "probability",
    [
        0.0,
        1.0,
        -0.1,
        1.1,
    ],
)
def test_probability_to_logit_rejects_out_of_range_values(
        probability: float,
) -> None:
    """测试拒绝超出区间的违约概率"""
    with pytest.raises(
            ValueError,
            match=r"probability 必须在 \(0, 1\) 区间内",
    ):
        ScoreTransformer.probability_to_logit(
            probability
        )


@pytest.mark.parametrize(
    "probability",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_probability_to_logit_rejects_non_finite_values(
        probability: float,
) -> None:
    """测试拒绝非有限违约概率"""
    with pytest.raises(
            ValueError,
            match="probability 必须是有限数值",
    ):
        ScoreTransformer.probability_to_logit(
            probability
        )


@pytest.mark.parametrize(
    "method_name",
    [
        "logit_to_score",
        "score_to_logit",
        "score_to_probability",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_instance_conversions_reject_non_finite_values(
        method_name: str,
        value: float,
        transformer: ScoreTransformer,
) -> None:
    """测试实例转换方法拒绝非有限数值"""
    method: Any = getattr(
        transformer,
        method_name,
    )

    parameter_name = (
        "logit"
        if method_name == "logit_to_score"
        else "score"
    )

    with pytest.raises(
            ValueError,
            match=f"{parameter_name} 必须是有限数值",
    ):
        method(
            value
        )


@pytest.mark.parametrize(
    "value",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_logit_to_probability_rejects_non_finite_values(
        value: float,
) -> None:
    """测试 Logit 转概率拒绝非有限数值"""
    with pytest.raises(
            ValueError,
            match="logit 必须是有限数值",
    ):
        ScoreTransformer.logit_to_probability(
            value
        )


def test_numeric_string_is_converted_to_float(
        transformer: ScoreTransformer,
) -> None:
    """测试运行时接受可转换为浮点数的值"""
    logit_input: Any = "1.25"
    score_input: Any = "650"

    assert transformer.logit_to_score(
        logit_input
    ) == pytest.approx(
        transformer.logit_to_score(
            1.25
        )
    )

    assert transformer.score_to_logit(
        score_input
    ) == pytest.approx(
        transformer.score_to_logit(
            650.0
        )
    )


@pytest.mark.parametrize(
    (
        "method_name",
        "value",
    ),
    [
        (
            "logit_to_score",
            "invalid",
        ),
        (
            "score_to_logit",
            None,
        ),
        (
            "probability_to_logit",
            object(),
        ),
    ],
)
def test_non_numeric_values_are_rejected(
        method_name: str,
        value: Any,
        transformer: ScoreTransformer,
) -> None:
    """测试拒绝无法转换为浮点数的值"""
    method: Any = getattr(
        transformer,
        method_name,
    )

    with pytest.raises(
            ValueError,
            match=(
                "probability|logit|score"
                ".*必须是数值"
            ),
    ):
        method(
            value
        )
