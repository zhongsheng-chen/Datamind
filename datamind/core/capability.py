# datamind/core/capability.py

"""模型能力和评分能力定义

定义模型推理能力和评分组件能力，实现模型类型与能力之间的解耦。

模型能力由具体模型适配器根据当前模型实例动态声明。

核心功能：
  - ModelCapability: 模型能力枚举
  - ScorecardCapability: 评分能力枚举
  - has_model_capability: 检查模型是否包含指定能力
  - has_scorecard_capability: 检查评分组件是否包含指定能力
  - has_all_model_capabilities: 检查模型是否包含全部指定能力
  - has_all_scorecard_capabilities: 检查评分组件是否包含全部指定能力
  - has_any_model_capability: 检查模型是否包含任意指定能力
  - has_any_scorecard_capability: 检查评分组件是否包含任意指定能力
  - combine_model_capabilities: 组合模型能力
  - combine_scorecard_capabilities: 组合评分能力
  - get_model_capability_list: 获取模型能力名称列表
  - get_scorecard_capability_list: 获取评分能力名称列表
  - get_model_capability_descriptions: 获取模型能力描述
  - get_scorecard_capability_descriptions: 获取评分能力描述
  - get_model_capability_summary: 获取模型能力摘要
  - get_scorecard_capability_summary: 获取评分能力摘要

使用示例：
  from datamind.core.capability import (
      ModelCapability,
      has_model_capability,
      has_all_model_capabilities,
      combine_model_capabilities,
      get_model_capability_list,
  )

  capabilities = (
      ModelCapability.PREDICT_PROBA
      | ModelCapability.PREDICT_LOG_ODDS
      | ModelCapability.BATCH_PREDICT
  )

  if has_model_capability(
      capabilities,
      ModelCapability.PREDICT_PROBA,
  ):
      print("支持概率预测")

  required = (
      ModelCapability.PREDICT_PROBA
      | ModelCapability.PREDICT_LOG_ODDS
  )

  if has_all_model_capabilities(
      capabilities,
      required,
  ):
      print("支持概率和 Logit 推理")

  names = get_model_capability_list(
      capabilities
  )

  print(names)
"""

from enum import IntFlag, auto
from typing import Any


class ModelCapability(IntFlag):
    """模型能力枚举

    使用 IntFlag 支持多个能力的组合和位运算判断。

    说明：
        Capability 表示 Datamind 当前统一接口真正暴露的能力，
        不代表底层机器学习框架理论上支持的全部功能。

        例如底层 CatBoost 或 XGBoost 可能具备 SHAP 能力，
        但只有 Datamind 对应适配器实现统一 SHAP 接口后，
        才应声明 SHAP 相关能力。

    属性：
        NONE:
            无能力

        PREDICT_PROBA:
            支持概率预测

        PREDICT_CLASS:
            支持直接分类标签预测

        PREDICT_LOG_ODDS:
            支持原始 Logit 或 Log Odds 输出

        SHAP:
            支持通用 SHAP 解释

        SHAP_TREE:
            支持 Tree SHAP 解释

        SHAP_KERNEL:
            支持 Kernel SHAP 解释

        FEATURE_IMPORTANCE:
            支持特征重要性

        BATCH_PREDICT:
            支持批量推理
    """

    NONE = 0

    PREDICT_PROBA = auto()
    PREDICT_CLASS = auto()
    PREDICT_LOG_ODDS = auto()

    SHAP = auto()
    SHAP_TREE = auto()
    SHAP_KERNEL = auto()

    FEATURE_IMPORTANCE = auto()
    BATCH_PREDICT = auto()


class ScorecardCapability(IntFlag):
    """评分能力枚举

    描述评分组件当前真正提供的能力。

    属性：
        NONE:
            无能力

        SCORECARD_WOE:
            WOE 转换

        SCORECARD_LOGIT:
            Logit 计算或获取

        SCORECARD_FEATURE_LOGIT:
            特征级 Logit 贡献

        SCORECARD_FEATURE_SCORE:
            特征级评分贡献

        SCORECARD_TOTAL_SCORE:
            总评分计算

        SCORECARD_EXPORT:
            评分卡导出
    """

    NONE = 0

    SCORECARD_WOE = auto()
    SCORECARD_LOGIT = auto()
    SCORECARD_FEATURE_LOGIT = auto()
    SCORECARD_FEATURE_SCORE = auto()
    SCORECARD_TOTAL_SCORE = auto()
    SCORECARD_EXPORT = auto()


_MODEL_CAPABILITY_DESCRIPTIONS: dict[
    ModelCapability,
    str,
] = {
    ModelCapability.PREDICT_PROBA:
        "概率预测",

    ModelCapability.PREDICT_CLASS:
        "分类标签预测",

    ModelCapability.PREDICT_LOG_ODDS:
        "原始 Logit 或 Log Odds 输出",

    ModelCapability.SHAP:
        "通用 SHAP 解释",

    ModelCapability.SHAP_TREE:
        "Tree SHAP 解释",

    ModelCapability.SHAP_KERNEL:
        "Kernel SHAP 解释",

    ModelCapability.FEATURE_IMPORTANCE:
        "特征重要性",

    ModelCapability.BATCH_PREDICT:
        "批量推理",
}


_SCORECARD_CAPABILITY_DESCRIPTIONS: dict[
    ScorecardCapability,
    str,
] = {
    ScorecardCapability.SCORECARD_WOE:
        "WOE 转换",

    ScorecardCapability.SCORECARD_LOGIT:
        "Logit 计算",

    ScorecardCapability.SCORECARD_FEATURE_LOGIT:
        "特征 Logit 贡献",

    ScorecardCapability.SCORECARD_FEATURE_SCORE:
        "特征评分贡献",

    ScorecardCapability.SCORECARD_TOTAL_SCORE:
        "总评分计算",

    ScorecardCapability.SCORECARD_EXPORT:
        "评分卡导出",
}


def has_model_capability(
    capabilities: ModelCapability,
    capability: ModelCapability,
) -> bool:
    """检查模型是否包含指定能力

    参数：
        capabilities: 模型能力集
        capability: 需要检查的能力

    返回：
        包含返回 True，否则返回 False
    """
    return bool(
        capabilities & capability
    )


def has_scorecard_capability(
    capabilities: ScorecardCapability,
    capability: ScorecardCapability,
) -> bool:
    """检查评分组件是否包含指定能力

    参数：
        capabilities: 评分能力集
        capability: 需要检查的能力

    返回：
        包含返回 True，否则返回 False
    """
    return bool(
        capabilities & capability
    )


def has_all_model_capabilities(
    capabilities: ModelCapability,
    required: ModelCapability,
) -> bool:
    """检查模型是否包含全部指定能力

    参数：
        capabilities: 当前模型能力集
        required: 所需能力组合

    返回：
        包含全部能力返回 True，否则返回 False
    """
    return (
        capabilities & required
    ) == required


def has_all_scorecard_capabilities(
    capabilities: ScorecardCapability,
    required: ScorecardCapability,
) -> bool:
    """检查评分组件是否包含全部指定能力

    参数：
        capabilities: 当前评分能力集
        required: 所需能力组合

    返回：
        包含全部能力返回 True，否则返回 False
    """
    return (
        capabilities & required
    ) == required


def has_any_model_capability(
    capabilities: ModelCapability,
    candidates: ModelCapability,
) -> bool:
    """检查模型是否包含任意指定能力

    参数：
        capabilities: 当前模型能力集
        candidates: 候选能力组合

    返回：
        包含任意能力返回 True，否则返回 False
    """
    return bool(
        capabilities & candidates
    )


def has_any_scorecard_capability(
    capabilities: ScorecardCapability,
    candidates: ScorecardCapability,
) -> bool:
    """检查评分组件是否包含任意指定能力

    参数：
        capabilities: 当前评分能力集
        candidates: 候选能力组合

    返回：
        包含任意能力返回 True，否则返回 False
    """
    return bool(
        capabilities & candidates
    )


def combine_model_capabilities(
    capabilities: list[ModelCapability],
) -> ModelCapability:
    """组合多个模型能力

    参数：
        capabilities: 模型能力列表

    返回：
        组合后的模型能力位掩码
    """
    result = ModelCapability.NONE

    for capability in capabilities:
        result |= capability

    return result


def combine_scorecard_capabilities(
    capabilities: list[ScorecardCapability],
) -> ScorecardCapability:
    """组合多个评分能力

    参数：
        capabilities: 评分能力列表

    返回：
        组合后的评分能力位掩码
    """
    result = ScorecardCapability.NONE

    for capability in capabilities:
        result |= capability

    return result


def get_model_capability_list(
    capabilities: ModelCapability,
) -> list[str]:
    """获取模型能力名称列表

    参数：
        capabilities: 模型能力集

    返回：
        当前已启用能力名称列表
    """
    result: list[str] = []

    for capability in ModelCapability:
        if capability == ModelCapability.NONE:
            continue

        if capabilities & capability:
            result.append(
                capability.name
            )

    return result


def get_scorecard_capability_list(
    capabilities: ScorecardCapability,
) -> list[str]:
    """获取评分能力名称列表

    参数：
        capabilities: 评分能力集

    返回：
        当前已启用能力名称列表
    """
    result: list[str] = []

    for capability in ScorecardCapability:
        if capability == ScorecardCapability.NONE:
            continue

        if capabilities & capability:
            result.append(
                capability.name
            )

    return result


def get_model_capability_descriptions(
    capabilities: ModelCapability,
) -> list[dict[str, str]]:
    """获取模型能力描述列表

    参数：
        capabilities: 模型能力集

    返回：
        包含 name 和 description 的列表
    """
    result: list[dict[str, str]] = []

    for capability in ModelCapability:
        if capability == ModelCapability.NONE:
            continue

        if capabilities & capability:
            result.append({
                "name": capability.name,
                "description": (
                    _MODEL_CAPABILITY_DESCRIPTIONS.get(
                        capability,
                        capability.name,
                    )
                ),
            })

    return result


def get_scorecard_capability_descriptions(
    capabilities: ScorecardCapability,
) -> list[dict[str, str]]:
    """获取评分能力描述列表

    参数：
        capabilities: 评分能力集

    返回：
        包含 name 和 description 的列表
    """
    result: list[dict[str, str]] = []

    for capability in ScorecardCapability:
        if capability == ScorecardCapability.NONE:
            continue

        if capabilities & capability:
            result.append({
                "name": capability.name,
                "description": (
                    _SCORECARD_CAPABILITY_DESCRIPTIONS.get(
                        capability,
                        capability.name,
                    )
                ),
            })

    return result


def get_model_capability_summary(
    capabilities: ModelCapability,
) -> dict[str, Any]:
    """获取模型能力摘要

    参数：
        capabilities: 模型能力集

    返回：
        能力名称、描述和数量摘要
    """
    names = get_model_capability_list(
        capabilities
    )

    descriptions = (
        get_model_capability_descriptions(
            capabilities
        )
    )

    return {
        "names": names,
        "descriptions": descriptions,
        "count": len(names),
    }


def get_scorecard_capability_summary(
    capabilities: ScorecardCapability,
) -> dict[str, Any]:
    """获取评分能力摘要

    参数：
        capabilities: 评分能力集

    返回：
        能力名称、描述和数量摘要
    """
    names = get_scorecard_capability_list(
        capabilities
    )

    descriptions = (
        get_scorecard_capability_descriptions(
            capabilities
        )
    )

    return {
        "names": names,
        "descriptions": descriptions,
        "count": len(names),
    }


__all__ = [
    "ModelCapability",
    "ScorecardCapability",
    "has_model_capability",
    "has_scorecard_capability",
    "has_all_model_capabilities",
    "has_all_scorecard_capabilities",
    "has_any_model_capability",
    "has_any_scorecard_capability",
    "combine_model_capabilities",
    "combine_scorecard_capabilities",
    "get_model_capability_list",
    "get_scorecard_capability_list",
    "get_model_capability_descriptions",
    "get_scorecard_capability_descriptions",
    "get_model_capability_summary",
    "get_scorecard_capability_summary",
]