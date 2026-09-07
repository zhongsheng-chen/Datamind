# datamind/core/capability.py

"""模型能力

定义统一模型接口的能力标记，并提供组合、查询和摘要生成工具。

核心功能：
  - has_model_capability: 检查指定能力
  - has_all_model_capabilities: 检查全部能力
  - has_any_model_capability: 检查任意能力
  - combine_model_capabilities: 组合模型能力
  - get_model_capability_list: 获取能力名称
  - get_model_capability_descriptions: 获取能力说明
  - get_model_capability_summary: 获取能力摘要

使用示例：
  from datamind.core.capability import ModelCapability

  capabilities = (
      ModelCapability.PREDICT_PROBA
      | ModelCapability.BATCH_PREDICT
  )
"""

from enum import (
    IntFlag,
    auto,
)
from typing import Any


class ModelCapability(IntFlag):
    """统一模型接口提供的能力

    属性：
        NONE: 不提供模型能力
        PREDICT_PROBA: 支持概率预测
        PREDICT_LOG_ODDS: 支持对数几率预测
        FEATURE_IMPORTANCE: 支持特征重要性
        BATCH_PREDICT: 支持批量预测
    """

    NONE = 0
    PREDICT_PROBA = auto()
    PREDICT_LOG_ODDS = auto()
    FEATURE_IMPORTANCE = auto()
    BATCH_PREDICT = auto()


_DESCRIPTIONS = {
    ModelCapability.PREDICT_PROBA: "概率预测",
    ModelCapability.PREDICT_LOG_ODDS: "对数几率预测",
    ModelCapability.FEATURE_IMPORTANCE: "特征重要性",
    ModelCapability.BATCH_PREDICT: "批量预测",
}


def has_model_capability(
        capabilities: ModelCapability,
        capability: ModelCapability,
) -> bool:
    """检查模型是否包含指定能力

    参数：
        capabilities: 模型能力集
        capability: 待检查的能力

    返回：
        包含指定能力时返回 True，否则返回 False
    """
    return bool(capabilities & capability)


def has_all_model_capabilities(
        capabilities: ModelCapability,
        required: ModelCapability,
) -> bool:
    """检查模型是否包含全部指定能力

    参数：
        capabilities: 模型能力集
        required: 必须同时包含的能力

    返回：
        包含全部能力时返回 True，否则返回 False
    """
    return capabilities & required == required


def has_any_model_capability(
        capabilities: ModelCapability,
        candidates: ModelCapability,
) -> bool:
    """检查模型是否包含任意指定能力

    参数：
        capabilities: 模型能力集
        candidates: 候选能力

    返回：
        包含任意候选能力时返回 True，否则返回 False
    """
    return bool(capabilities & candidates)


def combine_model_capabilities(
        capabilities: list[ModelCapability],
) -> ModelCapability:
    """组合模型能力

    参数：
        capabilities: 待组合的模型能力列表

    返回：
        组合后的模型能力集；空列表返回 ModelCapability.NONE
    """
    result = ModelCapability.NONE

    for capability in capabilities:
        result |= capability

    return result


def get_model_capability_list(
        capabilities: ModelCapability,
) -> list[str]:
    """获取已启用的模型能力名称

    参数：
        capabilities: 模型能力集

    返回：
        按枚举定义顺序排列的能力名称列表
    """
    return [
        str(capability.name)
        for capability in ModelCapability
        if (
            capability != ModelCapability.NONE
            and capabilities & capability
        )
    ]


def get_model_capability_descriptions(
        capabilities: ModelCapability,
) -> list[dict[str, str]]:
    """获取已启用模型能力的名称和说明

    参数：
        capabilities: 模型能力集

    返回：
        按枚举定义顺序排列的能力名称和说明列表
    """
    return [
        {
            "name": str(capability.name),
            "description": _DESCRIPTIONS.get(
                capability,
                str(capability.name),
            ),
        }
        for capability in ModelCapability
        if (
            capability != ModelCapability.NONE
            and capabilities & capability
        )
    ]


def get_model_capability_summary(
        capabilities: ModelCapability,
) -> dict[str, Any]:
    """获取模型能力摘要

    参数：
        capabilities: 模型能力集

    返回：
        包含能力名称、能力说明和能力数量的摘要
    """
    names = get_model_capability_list(capabilities)
    return {
        "names": names,
        "descriptions": get_model_capability_descriptions(
            capabilities
        ),
        "count": len(names),
    }


__all__ = [
    "ModelCapability",
    "has_model_capability",
    "has_all_model_capabilities",
    "has_any_model_capability",
    "combine_model_capabilities",
    "get_model_capability_list",
    "get_model_capability_descriptions",
    "get_model_capability_summary",
]
