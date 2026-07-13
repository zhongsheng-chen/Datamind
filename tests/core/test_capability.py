# tests/core/test_capability.py

"""模型能力和评分能力测试

验证模型能力、评分能力枚举，以及能力判断、组合、
名称列表、中文描述和摘要生成。

核心功能：
  - 验证能力枚举值
  - 验证单项能力判断
  - 验证全部能力判断
  - 验证任意能力判断
  - 验证能力组合
  - 验证能力名称列表
  - 验证能力描述
  - 验证能力摘要
"""

import pytest

from datamind.core.capability import (
    ModelCapability,
    ScorecardCapability,
    combine_model_capabilities,
    combine_scorecard_capabilities,
    get_model_capability_descriptions,
    get_model_capability_list,
    get_model_capability_summary,
    get_scorecard_capability_descriptions,
    get_scorecard_capability_list,
    get_scorecard_capability_summary,
    has_all_model_capabilities,
    has_all_scorecard_capabilities,
    has_any_model_capability,
    has_any_scorecard_capability,
    has_model_capability,
    has_scorecard_capability,
)


def test_model_capability_values_are_independent_flags(
) -> None:
    """测试模型能力使用独立二进制位"""
    assert ModelCapability.NONE.value == 0

    assert (
        ModelCapability.PREDICT_PROBA.value
        == 1
    )

    assert (
        ModelCapability.PREDICT_LOG_ODDS.value
        == 2
    )

    assert (
        ModelCapability.FEATURE_IMPORTANCE.value
        == 4
    )

    assert (
        ModelCapability.BATCH_PREDICT.value
        == 8
    )


def test_scorecard_capability_values_are_independent_flags(
) -> None:
    """测试评分能力使用独立二进制位"""
    assert ScorecardCapability.NONE.value == 0

    assert (
        ScorecardCapability.SCORECARD_LOGIT.value
        == 1
    )

    assert (
        ScorecardCapability.SCORECARD_FEATURE_SCORE.value
        == 2
    )

    assert (
        ScorecardCapability.SCORECARD_TOTAL_SCORE.value
        == 4
    )


def test_model_capability_names_are_stable(
) -> None:
    """测试模型能力名称"""
    assert (
        ModelCapability.PREDICT_PROBA.name
        == "PREDICT_PROBA"
    )

    assert (
        ModelCapability.PREDICT_LOG_ODDS.name
        == "PREDICT_LOG_ODDS"
    )

    assert (
        ModelCapability.FEATURE_IMPORTANCE.name
        == "FEATURE_IMPORTANCE"
    )

    assert (
        ModelCapability.BATCH_PREDICT.name
        == "BATCH_PREDICT"
    )


def test_scorecard_capability_names_are_stable(
) -> None:
    """测试评分能力名称"""
    assert (
        ScorecardCapability.SCORECARD_LOGIT.name
        == "SCORECARD_LOGIT"
    )

    assert (
        ScorecardCapability.SCORECARD_FEATURE_SCORE.name
        == "SCORECARD_FEATURE_SCORE"
    )

    assert (
        ScorecardCapability.SCORECARD_TOTAL_SCORE.name
        == "SCORECARD_TOTAL_SCORE"
    )


@pytest.mark.parametrize(
    (
        "capability",
        "expected",
    ),
    [
        (
            ModelCapability.PREDICT_PROBA,
            True,
        ),
        (
            ModelCapability.PREDICT_LOG_ODDS,
            False,
        ),
        (
            ModelCapability.FEATURE_IMPORTANCE,
            True,
        ),
        (
            ModelCapability.BATCH_PREDICT,
            False,
        ),
        (
            ModelCapability.NONE,
            False,
        ),
    ],
)
def test_has_model_capability(
        capability: ModelCapability,
        expected: bool,
) -> None:
    """测试模型单项能力判断"""
    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
    )

    assert (
        has_model_capability(
            capabilities,
            capability,
        )
        is expected
    )


@pytest.mark.parametrize(
    (
        "capability",
        "expected",
    ),
    [
        (
            ScorecardCapability.SCORECARD_LOGIT,
            False,
        ),
        (
            ScorecardCapability.SCORECARD_FEATURE_SCORE,
            True,
        ),
        (
            ScorecardCapability.SCORECARD_TOTAL_SCORE,
            True,
        ),
        (
            ScorecardCapability.NONE,
            False,
        ),
    ],
)
def test_has_scorecard_capability(
        capability: ScorecardCapability,
        expected: bool,
) -> None:
    """测试评分单项能力判断"""
    capabilities = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert (
        has_scorecard_capability(
            capabilities,
            capability,
        )
        is expected
    )


def test_has_all_model_capabilities(
) -> None:
    """测试模型必须包含全部所需能力"""
    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.BATCH_PREDICT
    )

    required = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    missing = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
    )

    assert has_all_model_capabilities(
        capabilities,
        required,
    )

    assert not has_all_model_capabilities(
        capabilities,
        missing,
    )

    assert has_all_model_capabilities(
        capabilities,
        ModelCapability.NONE,
    )


def test_has_all_scorecard_capabilities(
) -> None:
    """测试评分组件必须包含全部所需能力"""
    capabilities = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    required = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    missing = (
        ScorecardCapability.SCORECARD_LOGIT
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert has_all_scorecard_capabilities(
        capabilities,
        required,
    )

    assert not has_all_scorecard_capabilities(
        capabilities,
        missing,
    )

    assert has_all_scorecard_capabilities(
        capabilities,
        ScorecardCapability.NONE,
    )


def test_has_any_model_capability(
) -> None:
    """测试模型包含任意候选能力"""
    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    candidates = (
        ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    missing = (
        ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.FEATURE_IMPORTANCE
    )

    assert has_any_model_capability(
        capabilities,
        candidates,
    )

    assert not has_any_model_capability(
        capabilities,
        missing,
    )

    assert not has_any_model_capability(
        capabilities,
        ModelCapability.NONE,
    )


def test_has_any_scorecard_capability(
) -> None:
    """测试评分组件包含任意候选能力"""
    capabilities = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    candidates = (
        ScorecardCapability.SCORECARD_LOGIT
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert has_any_scorecard_capability(
        capabilities,
        candidates,
    )

    assert not has_any_scorecard_capability(
        capabilities,
        ScorecardCapability.SCORECARD_LOGIT,
    )

    assert not has_any_scorecard_capability(
        capabilities,
        ScorecardCapability.NONE,
    )


def test_combine_model_capabilities(
) -> None:
    """测试组合模型能力"""
    result = combine_model_capabilities([
        ModelCapability.PREDICT_PROBA,
        ModelCapability.PREDICT_LOG_ODDS,
        ModelCapability.PREDICT_PROBA,
        ModelCapability.BATCH_PREDICT,
    ])

    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.BATCH_PREDICT
    )

    assert result == expected


def test_combine_model_capabilities_returns_none_for_empty_list(
) -> None:
    """测试空列表组合为 NONE"""
    assert (
        combine_model_capabilities([])
        == ModelCapability.NONE
    )


def test_combine_scorecard_capabilities(
) -> None:
    """测试组合评分能力"""
    result = combine_scorecard_capabilities([
        ScorecardCapability.SCORECARD_FEATURE_SCORE,
        ScorecardCapability.SCORECARD_TOTAL_SCORE,
        ScorecardCapability.SCORECARD_FEATURE_SCORE,
    ])

    expected = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert result == expected


def test_combine_scorecard_capabilities_returns_none_for_empty_list(
) -> None:
    """测试空列表组合为 NONE"""
    assert (
        combine_scorecard_capabilities([])
        == ScorecardCapability.NONE
    )


def test_get_model_capability_list_preserves_enum_order(
) -> None:
    """测试模型能力名称按照枚举顺序返回"""
    capabilities = (
        ModelCapability.BATCH_PREDICT
        | ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
    )

    assert get_model_capability_list(
        capabilities
    ) == [
        "PREDICT_PROBA",
        "FEATURE_IMPORTANCE",
        "BATCH_PREDICT",
    ]


def test_get_model_capability_list_returns_empty_for_none(
) -> None:
    """测试 NONE 返回空模型能力名称列表"""
    assert get_model_capability_list(
        ModelCapability.NONE
    ) == []


def test_get_scorecard_capability_list_preserves_enum_order(
) -> None:
    """测试评分能力名称按照枚举顺序返回"""
    capabilities = (
        ScorecardCapability.SCORECARD_TOTAL_SCORE
        | ScorecardCapability.SCORECARD_LOGIT
    )

    assert get_scorecard_capability_list(
        capabilities
    ) == [
        "SCORECARD_LOGIT",
        "SCORECARD_TOTAL_SCORE",
    ]


def test_get_scorecard_capability_list_returns_empty_for_none(
) -> None:
    """测试 NONE 返回空评分能力名称列表"""
    assert get_scorecard_capability_list(
        ScorecardCapability.NONE
    ) == []


def test_get_model_capability_descriptions(
) -> None:
    """测试模型能力中文描述"""
    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert get_model_capability_descriptions(
        capabilities
    ) == [
        {
            "name": "PREDICT_PROBA",
            "description": "概率预测",
        },
        {
            "name": "PREDICT_LOG_ODDS",
            "description": (
                "原始 Logit 或 Log Odds 输出"
            ),
        },
        {
            "name": "FEATURE_IMPORTANCE",
            "description": "特征重要性",
        },
        {
            "name": "BATCH_PREDICT",
            "description": "批量推理",
        },
    ]


def test_get_scorecard_capability_descriptions(
) -> None:
    """测试评分能力中文描述"""
    capabilities = (
        ScorecardCapability.SCORECARD_LOGIT
        | ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert get_scorecard_capability_descriptions(
        capabilities
    ) == [
        {
            "name": "SCORECARD_LOGIT",
            "description": "Logit 计算",
        },
        {
            "name": "SCORECARD_FEATURE_SCORE",
            "description": "特征评分贡献",
        },
        {
            "name": "SCORECARD_TOTAL_SCORE",
            "description": "总评分计算",
        },
    ]


def test_capability_descriptions_return_empty_for_none(
) -> None:
    """测试 NONE 返回空能力描述列表"""
    assert get_model_capability_descriptions(
        ModelCapability.NONE
    ) == []

    assert get_scorecard_capability_descriptions(
        ScorecardCapability.NONE
    ) == []


def test_get_model_capability_summary(
) -> None:
    """测试模型能力摘要"""
    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    assert get_model_capability_summary(
        capabilities
    ) == {
        "names": [
            "PREDICT_PROBA",
            "BATCH_PREDICT",
        ],
        "descriptions": [
            {
                "name": "PREDICT_PROBA",
                "description": "概率预测",
            },
            {
                "name": "BATCH_PREDICT",
                "description": "批量推理",
            },
        ],
        "count": 2,
    }


def test_get_scorecard_capability_summary(
) -> None:
    """测试评分能力摘要"""
    capabilities = (
        ScorecardCapability.SCORECARD_FEATURE_SCORE
        | ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert get_scorecard_capability_summary(
        capabilities
    ) == {
        "names": [
            "SCORECARD_FEATURE_SCORE",
            "SCORECARD_TOTAL_SCORE",
        ],
        "descriptions": [
            {
                "name": "SCORECARD_FEATURE_SCORE",
                "description": "特征评分贡献",
            },
            {
                "name": "SCORECARD_TOTAL_SCORE",
                "description": "总评分计算",
            },
        ],
        "count": 2,
    }


def test_capability_summary_is_empty_for_none(
) -> None:
    """测试 NONE 返回空能力摘要"""
    assert get_model_capability_summary(
        ModelCapability.NONE
    ) == {
        "names": [],
        "descriptions": [],
        "count": 0,
    }

    assert get_scorecard_capability_summary(
        ScorecardCapability.NONE
    ) == {
        "names": [],
        "descriptions": [],
        "count": 0,
    }
