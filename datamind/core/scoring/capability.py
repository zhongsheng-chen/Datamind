# Datamind/datamind/core/scoring/capability.py

"""评分卡模型能力定义

定义评分卡模型支持的各种能力，实现模型类型与能力的解耦。

核心功能：
  - infer_capabilities: 根据适配器声明推断能力集
  - has_capability: 检查是否包含指定能力
  - get_capability_list: 获取能力名称列表（用于序列化）
  - validate_required_capabilities: 验证必需能力
  - combine_capabilities: 组合多个能力
  - get_capability_weight: 获取能力权重（用于优先级排序）

设计原则：
  - capability 只回答"支持什么"，不做执行校验
  - 优先使用适配器的 SUPPORTED_CAPABILITIES 声明
  - fallback 仅限安全推断，PREDICT_CLASS 必须声明
  - 声明一旦存在，必须正确（Fail Fast）
  - PREDICT_PROBA 是系统强约束，适配器不得声明

能力分类：
  - 基础能力（强约束）：PREDICT_PROBA（系统注入，适配器不可声明）
  - 核心能力：PREDICT_SCORE、PREDICT_CLASS
  - 评分卡能力：FEATURE_SCORE
  - 解释能力：SHAP、FEATURE_IMPORTANCE
  - 工程能力：EXPORT_SCORECARD、BATCH_PREDICT
"""

from enum import IntFlag, auto
from typing import List, Dict, Set, Union


class ScorecardCapability(IntFlag):
    """评分卡模型能力枚举

    使用 IntFlag 支持位运算，可高效组合和判断多个能力。

    属性:
        NONE: 无能力
        PREDICT_PROBA: 输出违约概率（强约束，系统注入，适配器不可声明）
        PREDICT_SCORE: 输出信用评分
        PREDICT_CLASS: 输出分类标签（0/1）
        FEATURE_SCORE: 支持特征分计算
        SHAP: 支持 SHAP 值解释
        FEATURE_IMPORTANCE: 支持全局特征重要性
        EXPORT_SCORECARD: 支持导出评分卡
        BATCH_PREDICT: 支持批量预测
    """
    NONE = 0
    PREDICT_PROBA = auto()
    PREDICT_SCORE = auto()
    PREDICT_CLASS = auto()
    FEATURE_SCORE = auto()
    SHAP = auto()
    FEATURE_IMPORTANCE = auto()
    EXPORT_SCORECARD = auto()
    BATCH_PREDICT = auto()


# 能力名称映射
_CAPABILITY_NAMES = {
    ScorecardCapability.PREDICT_PROBA: "PREDICT_PROBA",
    ScorecardCapability.PREDICT_SCORE: "PREDICT_SCORE",
    ScorecardCapability.PREDICT_CLASS: "PREDICT_CLASS",
    ScorecardCapability.FEATURE_SCORE: "FEATURE_SCORE",
    ScorecardCapability.SHAP: "SHAP",
    ScorecardCapability.FEATURE_IMPORTANCE: "FEATURE_IMPORTANCE",
    ScorecardCapability.EXPORT_SCORECARD: "EXPORT_SCORECARD",
    ScorecardCapability.BATCH_PREDICT: "BATCH_PREDICT",
}

# 能力描述映射
_CAPABILITY_DESCRIPTIONS = {
    ScorecardCapability.PREDICT_PROBA: "违约概率",
    ScorecardCapability.PREDICT_SCORE: "信用评分",
    ScorecardCapability.PREDICT_CLASS: "分类结果",
    ScorecardCapability.FEATURE_SCORE: "特征分",
    ScorecardCapability.SHAP: "SHAP解释",
    ScorecardCapability.FEATURE_IMPORTANCE: "特征重要性",
    ScorecardCapability.EXPORT_SCORECARD: "导出评分卡",
    ScorecardCapability.BATCH_PREDICT: "批量预测",
}

# 能力权重（用于优先级排序，数值越大优先级越高）
_CAPABILITY_WEIGHTS = {
    ScorecardCapability.PREDICT_PROBA: 100,
    ScorecardCapability.PREDICT_SCORE: 90,
    ScorecardCapability.PREDICT_CLASS: 80,
    ScorecardCapability.FEATURE_SCORE: 70,
    ScorecardCapability.SHAP: 60,
    ScorecardCapability.FEATURE_IMPORTANCE: 50,
    ScorecardCapability.EXPORT_SCORECARD: 40,
    ScorecardCapability.BATCH_PREDICT: 30,
}

ALL_CAPABILITIES: List[ScorecardCapability] = [
    ScorecardCapability.PREDICT_PROBA,
    ScorecardCapability.PREDICT_SCORE,
    ScorecardCapability.PREDICT_CLASS,
    ScorecardCapability.FEATURE_SCORE,
    ScorecardCapability.SHAP,
    ScorecardCapability.FEATURE_IMPORTANCE,
    ScorecardCapability.EXPORT_SCORECARD,
    ScorecardCapability.BATCH_PREDICT,
]

_REQUIRED_CAPABILITIES: Set[ScorecardCapability] = {
    ScorecardCapability.PREDICT_PROBA,
}


def infer_capabilities(adapter) -> ScorecardCapability:
    """
    根据适配器声明推断能力集

    参数:
        adapter: 模型适配器实例

    返回:
        ScorecardCapability 位掩码

    异常:
        RuntimeError: 缺少必需能力（PREDICT_PROBA）
        TypeError: SUPPORTED_CAPABILITIES 类型错误
        ValueError: SUPPORTED_CAPABILITIES 包含 PREDICT_PROBA
    """
    caps = ScorecardCapability.NONE

    # 强约束：必须实现 predict_proba
    if not hasattr(adapter, "predict_proba"):
        raise RuntimeError("模型适配器必须实现 predict_proba 方法")

    caps |= ScorecardCapability.PREDICT_PROBA

    # 声明优先
    declared = getattr(adapter, "SUPPORTED_CAPABILITIES", None)

    if declared is not None:
        if not isinstance(declared, ScorecardCapability):
            raise TypeError(
                f"SUPPORTED_CAPABILITIES 必须是 ScorecardCapability 类型，当前: {type(declared)}"
            )

        # PREDICT_PROBA 是系统强约束，适配器不得声明
        if declared & ScorecardCapability.PREDICT_PROBA:
            raise ValueError(
                "PREDICT_PROBA 为系统强约束能力，不应在 SUPPORTED_CAPABILITIES 中声明"
            )

        return caps | declared

    # fallback（仅安全推断，不推断 PREDICT_CLASS）
    if hasattr(adapter, "predict_score"):
        caps |= ScorecardCapability.PREDICT_SCORE

    if hasattr(adapter, "get_feature_score"):
        caps |= ScorecardCapability.FEATURE_SCORE

    if hasattr(adapter, "get_shap_values"):
        caps |= ScorecardCapability.SHAP

    if hasattr(adapter, "get_feature_importance"):
        caps |= ScorecardCapability.FEATURE_IMPORTANCE

    if hasattr(adapter, "predict_proba_batch"):
        caps |= ScorecardCapability.BATCH_PREDICT

    if hasattr(adapter, "export_scorecard"):
        caps |= ScorecardCapability.EXPORT_SCORECARD

    return caps


def has_capability(caps: ScorecardCapability, capability: ScorecardCapability) -> bool:
    """
    检查是否包含指定能力

    参数:
        caps: 能力集（位掩码）
        capability: 要检查的能力

    返回:
        True 表示包含该能力，False 表示不包含
    """
    return bool(caps & capability)


def has_all_capabilities(
    caps: ScorecardCapability,
    required: ScorecardCapability
) -> bool:
    """
    检查是否包含所有指定能力

    参数:
        caps: 能力集（位掩码）
        required: 必需的能力集

    返回:
        True 表示包含所有能力，False 表示缺少至少一个
    """
    return (caps & required) == required


def has_any_capability(
    caps: ScorecardCapability,
    capabilities: ScorecardCapability
) -> bool:
    """
    检查是否包含任意一个指定能力

    参数:
        caps: 能力集（位掩码）
        capabilities: 待检查的能力集

    返回:
        True 表示包含至少一个能力，False 表示不包含任何能力
    """
    return bool(caps & capabilities)


def combine_capabilities(capabilities: List[ScorecardCapability]) -> ScorecardCapability:
    """
    组合多个能力

    参数:
        capabilities: 能力列表

    返回:
        组合后的能力集
    """
    result = ScorecardCapability.NONE
    for cap in capabilities:
        result |= cap
    return result


def get_capability_weight(capability: ScorecardCapability) -> int:
    """
    获取能力权重（用于优先级排序）

    参数:
        capability: 能力枚举

    返回:
        权重值（数值越大优先级越高）
    """
    return _CAPABILITY_WEIGHTS.get(capability, 0)


def get_capability_weight_sum(caps: ScorecardCapability) -> int:
    """
    获取能力集的总权重

    参数:
        caps: 能力集（位掩码）

    返回:
        总权重值
    """
    total = 0
    for cap in ALL_CAPABILITIES:
        if caps & cap:
            total += _CAPABILITY_WEIGHTS.get(cap, 0)
    return total


def sort_by_capability_weight(
    items: List[any],
    key_func: callable
) -> List[any]:
    """
    根据能力权重对项目列表排序

    参数:
        items: 待排序的项目列表
        key_func: 提取能力集的函数

    返回:
        排序后的列表（权重高的在前）
    """
    return sorted(
        items,
        key=lambda x: get_capability_weight_sum(key_func(x)),
        reverse=True
    )


def validate_required_capabilities(caps: ScorecardCapability) -> None:
    """
    验证必需能力是否存在

    参数:
        caps: 能力集（位掩码）

    异常:
        RuntimeError: 缺少必需能力
    """
    missing = [
        _CAPABILITY_NAMES[cap] for cap in _REQUIRED_CAPABILITIES
        if not has_capability(caps, cap)
    ]
    if missing:
        raise RuntimeError(f"模型缺少必需能力: {missing}")


def get_capability_list(caps: ScorecardCapability) -> List[str]:
    """
    获取能力名称列表（用于序列化）

    参数:
        caps: 能力集（位掩码）

    返回:
        能力名称列表
    """
    result: List[str] = []
    for cap in ALL_CAPABILITIES:
        if caps & cap:
            result.append(_CAPABILITY_NAMES[cap])
    return result


def get_capability_descriptions(caps: ScorecardCapability) -> List[Dict[str, str]]:
    """
    获取能力描述列表（用于 API 响应）

    参数:
        caps: 能力集（位掩码）

    返回:
        能力描述列表，每项包含 name 和 description
    """
    result: List[Dict[str, str]] = []
    for cap in ALL_CAPABILITIES:
        if caps & cap:
            result.append({
                "name": _CAPABILITY_NAMES[cap],
                "description": _CAPABILITY_DESCRIPTIONS.get(cap, _CAPABILITY_NAMES[cap])
            })
    return result


__all__ = [
    'ScorecardCapability',
    'ALL_CAPABILITIES',
    'infer_capabilities',
    'has_capability',
    'has_all_capabilities',
    'has_any_capability',
    'combine_capabilities',
    'get_capability_weight',
    'get_capability_weight_sum',
    'sort_by_capability_weight',
    'validate_required_capabilities',
    'get_capability_list',
    'get_capability_descriptions',
]