"""模型能力工具测试.

验证模型能力的组合、查询、描述和摘要生成。

核心功能：
  - test_model_capability_helpers:
    验证模型能力组合与查询
  - test_model_capability_summary:
    验证模型能力描述与摘要
"""

from datamind.core.capability import (
    ModelCapability,
    combine_model_capabilities,
    get_model_capability_descriptions,
    get_model_capability_list,
    get_model_capability_summary,
    has_all_model_capabilities,
    has_any_model_capability,
    has_model_capability,
)


def test_model_capability_helpers() -> None:
    """测试模型能力组合与查询."""
    capabilities = combine_model_capabilities([
        ModelCapability.PREDICT_PROBA,
        ModelCapability.BATCH_PREDICT,
    ])

    assert has_model_capability(
        capabilities,
        ModelCapability.PREDICT_PROBA,
    )
    assert has_all_model_capabilities(
        capabilities,
        (
            ModelCapability.PREDICT_PROBA
            | ModelCapability.BATCH_PREDICT
        ),
    )
    assert has_any_model_capability(
        capabilities,
        ModelCapability.FEATURE_IMPORTANCE,
    ) is False
    assert get_model_capability_list(capabilities) == [
        "PREDICT_PROBA",
        "BATCH_PREDICT",
    ]


def test_model_capability_summary() -> None:
    """测试模型能力摘要."""
    capabilities = combine_model_capabilities([
        ModelCapability.PREDICT_PROBA,
        ModelCapability.PREDICT_LOG_ODDS,
        ModelCapability.FEATURE_IMPORTANCE,
        ModelCapability.BATCH_PREDICT,
    ])
    descriptions = get_model_capability_descriptions(capabilities)

    assert descriptions == [
        {
            "name": "PREDICT_PROBA",
            "description": "概率预测",
        },
        {
            "name": "PREDICT_LOG_ODDS",
            "description": "对数几率预测",
        },
        {
            "name": "FEATURE_IMPORTANCE",
            "description": "特征重要性",
        },
        {
            "name": "BATCH_PREDICT",
            "description": "批量预测",
        },
    ]
    assert get_model_capability_summary(capabilities) == {
        "names": [
            "PREDICT_PROBA",
            "PREDICT_LOG_ODDS",
            "FEATURE_IMPORTANCE",
            "BATCH_PREDICT",
        ],
        "descriptions": descriptions,
        "count": 4,
    }
