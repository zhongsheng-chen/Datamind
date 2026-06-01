# datamind/core/capability.py

"""模型能力和评分卡能力定义

定义模型支持的各种能力和评分卡系统的能力，实现模型类型与能力的解耦。

核心功能：
  - has_model_capability: 检查模型是否包含指定能力
  - has_scorecard_capability: 检查评分卡是否包含指定能力
  - has_all_model_capabilities: 检查模型是否包含所有指定能力
  - has_all_scorecard_capabilities: 检查评分卡是否包含所有指定能力
  - has_any_model_capability: 检查模型是否包含任意指定能力
  - has_any_scorecard_capability: 检查评分卡是否包含任意指定能力
  - combine_model_capabilities: 组合多个模型能力
  - combine_scorecard_capabilities: 组合多个评分卡能力
  - get_model_capability_list: 获取模型能力名称列表
  - get_scorecard_capability_list: 获取评分卡能力名称列表
  - get_model_capability_descriptions: 获取模型能力描述列表
  - get_scorecard_capability_descriptions: 获取评分卡能力描述列表
  - get_model_capability_summary: 获取模型能力摘要
  - get_scorecard_capability_summary: 获取评分卡能力摘要

使用示例：
    from datamind.core.capability import (
        ModelCapability, ScorecardCapability,
        has_model_capability, has_all_model_capabilities,
        combine_model_capabilities, get_model_capability_list
    )

    # 定义模型支持的能力（使用位或运算组合）
    supported_caps = (
        ModelCapability.PREDICT_CLASS |
        ModelCapability.BATCH_PREDICT
    )

    # 检查是否包含指定能力
    if has_model_capability(supported_caps, ModelCapability.PREDICT_PROBA):
        print("支持概率预测")
    else:
        print("不支持概率预测")

    # 检查是否包含所有指定能力
    required = ModelCapability.PREDICT_PROBA | ModelCapability.PREDICT_CLASS
    if has_all_model_capabilities(supported_caps, required):
        print("支持所有必需能力")

    # 检查是否包含任意指定能力
    any_cap = ModelCapability.SHAP | ModelCapability.FEATURE_IMPORTANCE
    if has_any_model_capability(supported_caps, any_cap):
        print("支持解释能力")

    # 组合多个能力
    caps = combine_model_capabilities([
        ModelCapability.PREDICT_PROBA,
        ModelCapability.SHAP
    ])

    # 获取能力列表
    capability_names = get_model_capability_list(supported_caps)
    print(f"支持的能力: {capability_names}")

    # 获取能力摘要
    summary = get_model_capability_summary(supported_caps)
    print(f"共支持 {summary['count']} 项能力")
"""

from enum import IntFlag, auto
from typing import Any


class ModelCapability(IntFlag):
    """模型能力枚举

    使用 IntFlag 支持位运算，可高效组合和判断多个能力。

    属性:
        NONE: 无能力
        PREDICT_PROBA: 违约概率
        PREDICT_CLASS: 分类标签
        PREDICT_LOG_ODDS: 原始对数几率
        SHAP: SHAP 解释
        SHAP_TREE: SHAP 树解释
        SHAP_KERNEL: SHAP 核解释
        FEATURE_IMPORTANCE: 特征重要性
        BATCH_PREDICT: 批量预测
    """
    NONE = 0

    PREDICT_PROBA = auto()      # 违约概率
    PREDICT_CLASS = auto()      # 分类标签
    PREDICT_LOG_ODDS = auto()   # 原始对数几率
    SHAP = auto()               # SHAP 解释
    SHAP_TREE = auto()          # SHAP 树解释
    SHAP_KERNEL = auto()        # SHAP 核解释
    FEATURE_IMPORTANCE = auto() # 特征重要性
    BATCH_PREDICT = auto()      # 批量预测


class ScorecardCapability(IntFlag):
    """评分卡能力枚举

    描述评分卡的各层能力。

    属性:
        NONE: 无能力
        SCORECARD_WOE: WOE 转换
        SCORECARD_LOGIT: 对数几率
        SCORECARD_FEATURE_LOGIT: 特征对数几率
        SCORECARD_FEATURE_SCORE: 特征分数
        SCORECARD_TOTAL_SCORE: 评分卡分数
        SCORECARD_EXPORT: 评分卡导出
    """
    NONE = 0

    SCORECARD_WOE = auto()              # WOE 转换
    SCORECARD_LOGIT = auto()            # 对数几率
    SCORECARD_FEATURE_LOGIT = auto()    # 特征对数几率
    SCORECARD_FEATURE_SCORE = auto()    # 特征分数
    SCORECARD_TOTAL_SCORE = auto()      # 评分卡分数
    SCORECARD_EXPORT = auto()           # 评分卡导出


# 能力描述映射
_MODEL_CAPABILITY_DESCRIPTIONS: dict[ModelCapability, str] = {
    ModelCapability.PREDICT_PROBA: "违约概率",
    ModelCapability.PREDICT_CLASS: "分类标签",
    ModelCapability.PREDICT_LOG_ODDS: "原始对数几率",
    ModelCapability.SHAP: "SHAP 解释",
    ModelCapability.SHAP_TREE: "SHAP 树解释",
    ModelCapability.SHAP_KERNEL: "SHAP 核解释",
    ModelCapability.FEATURE_IMPORTANCE: "特征重要性",
    ModelCapability.BATCH_PREDICT: "批量预测",
}

_SCORECARD_CAPABILITY_DESCRIPTIONS: dict[ScorecardCapability, str] = {
    ScorecardCapability.SCORECARD_WOE: "WOE 转换",
    ScorecardCapability.SCORECARD_LOGIT: "对数几率",
    ScorecardCapability.SCORECARD_FEATURE_LOGIT: "特征对数几率",
    ScorecardCapability.SCORECARD_FEATURE_SCORE: "特征分数",
    ScorecardCapability.SCORECARD_TOTAL_SCORE: "评分卡分数",
    ScorecardCapability.SCORECARD_EXPORT: "评分卡导出",
}


def has_model_capability(caps: ModelCapability, capability: ModelCapability) -> bool:
    """检查模型是否包含指定能力

    参数：
        caps: 能力集位掩码
        capability: 要检查的单个能力

    返回：
        包含返回 True，否则返回 False
    """
    return bool(caps & capability)


def has_scorecard_capability(caps: ScorecardCapability, capability: ScorecardCapability) -> bool:
    """检查评分卡是否包含指定能力

    参数：
        caps: 能力集位掩码
        capability: 要检查的单个能力

    返回：
        包含返回 True，否则返回 False
    """
    return bool(caps & capability)


def has_all_model_capabilities(caps: ModelCapability, required: ModelCapability) -> bool:
    """检查模型是否包含所有指定能力

    参数：
        caps: 能力集位掩码
        required: 需要检查的能力位掩码（可包含多个能力）

    返回：
        包含所有能力返回 True，否则返回 False
    """
    return (caps & required) == required


def has_all_scorecard_capabilities(caps: ScorecardCapability, required: ScorecardCapability) -> bool:
    """检查评分卡是否包含所有指定能力

    参数：
        caps: 能力集位掩码
        required: 需要检查的能力位掩码（可包含多个能力）

    返回：
        包含所有能力返回 True，否则返回 False
    """
    return (caps & required) == required


def has_any_model_capability(caps: ModelCapability, capabilities: ModelCapability) -> bool:
    """检查模型是否包含任意一个指定能力

    参数：
        caps: 能力集位掩码
        capabilities: 需要检查的能力位掩码（可包含多个能力）

    返回：
        包含任意一个返回 True，否则返回 False
    """
    return bool(caps & capabilities)


def has_any_scorecard_capability(caps: ScorecardCapability, capabilities: ScorecardCapability) -> bool:
    """检查评分卡是否包含任意一个指定能力

    参数：
        caps: 能力集位掩码
        capabilities: 需要检查的能力位掩码（可包含多个能力）

    返回：
        包含任意一个返回 True，否则返回 False
    """
    return bool(caps & capabilities)


def combine_model_capabilities(capabilities: list[ModelCapability]) -> ModelCapability:
    """组合多个模型能力为位掩码

    参数：
        capabilities: 模型能力列表

    返回：
        组合后的位掩码
    """
    result = ModelCapability.NONE
    for cap in capabilities:
        result |= cap
    return result


def combine_scorecard_capabilities(capabilities: list[ScorecardCapability]) -> ScorecardCapability:
    """组合多个评分卡能力为位掩码

    参数：
        capabilities: 评分卡能力列表

    返回：
        组合后的位掩码
    """
    result = ScorecardCapability.NONE
    for cap in capabilities:
        result |= cap
    return result


def get_model_capability_list(caps: ModelCapability) -> list[str]:
    """获取模型能力名称列表

    遍历 ModelCapability 枚举的所有能力（排除 NONE），
    返回在位掩码中启用的能力名称列表。

    参数：
        caps: 能力位掩码

    返回：
        能力名称列表
    """
    result: list[str] = []

    for cap in ModelCapability:
        if cap == ModelCapability.NONE:
            continue

        if caps & cap:
            result.append(str(cap.name))

    return result


def get_scorecard_capability_list(caps: ScorecardCapability) -> list[str]:
    """获取评分卡能力名称列表

    遍历 ScorecardCapability 枚举的所有能力（排除 NONE），
    返回在位掩码中启用的能力名称列表。

    参数：
        caps: 能力位掩码

    返回：
        能力名称列表
    """
    result: list[str] = []

    for cap in ScorecardCapability:
        if cap == ScorecardCapability.NONE:
            continue

        if caps & cap:
            result.append(str(cap.name))

    return result


def get_model_capability_descriptions(caps: ModelCapability) -> list[dict[str, str]]:
    """获取模型能力描述列表

    参数：
        caps: 能力位掩码

    返回：
        包含 name 和 description 的字典列表
    """
    result: list[dict[str, str]] = []

    for cap in ModelCapability:
        if cap == ModelCapability.NONE:
            continue

        if caps & cap:
            result.append({
                "name": cap.name,
                "description": _MODEL_CAPABILITY_DESCRIPTIONS.get(cap, cap.name)
            })
    return result


def get_scorecard_capability_descriptions(caps: ScorecardCapability) -> list[dict[str, str]]:
    """获取评分卡能力描述列表

    参数：
        caps: 能力位掩码

    返回：
        包含 name 和 description 的字典列表
    """
    result: list[dict[str, str]] = []

    for cap in ScorecardCapability:
        if cap == ScorecardCapability.NONE:
            continue

        if caps & cap:
            result.append({
                "name": cap.name,
                "description": _SCORECARD_CAPABILITY_DESCRIPTIONS.get(cap, cap.name)
            })
    return result


def get_model_capability_summary(caps: ModelCapability) -> dict[str, Any]:
    """获取模型能力摘要

    参数：
        caps: 能力位掩码

    返回：
        包含名称列表和数量统计的摘要字典
    """
    names = get_model_capability_list(caps)
    return {
        "names": names,
        "count": len(names),
    }


def get_scorecard_capability_summary(caps: ScorecardCapability) -> dict[str, Any]:
    """获取评分卡能力摘要

    参数：
        caps: 能力位掩码

    返回：
        包含名称列表和数量统计的摘要字典
    """
    names = get_scorecard_capability_list(caps)
    return {
        "names": names,
        "count": len(names),
    }


__all__ = [
    'ModelCapability',
    'ScorecardCapability',
    'has_model_capability',
    'has_scorecard_capability',
    'has_all_model_capabilities',
    'has_all_scorecard_capabilities',
    'has_any_model_capability',
    'has_any_scorecard_capability',
    'combine_model_capabilities',
    'combine_scorecard_capabilities',
    'get_model_capability_list',
    'get_scorecard_capability_list',
    'get_model_capability_descriptions',
    'get_scorecard_capability_descriptions',
    'get_model_capability_summary',
    'get_scorecard_capability_summary',
]