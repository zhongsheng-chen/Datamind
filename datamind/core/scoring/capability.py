# datamind/core/scoring/capability.py

"""模型能力和评分卡能力定义

定义模型支持的各种能力和评分卡系统的能力，实现模型类型与能力的解耦。

核心功能：
  - infer_model_capabilities: 根据适配器声明推断模型能力集
  - infer_scorecard_capabilities: 根据评分卡引擎推断评分卡能力集
  - has_capability: 检查是否包含指定能力
  - has_all_capabilities: 检查是否包含所有指定能力
  - has_any_capability: 检查是否包含任意指定能力
  - expand_capabilities: 根据依赖关系自动补全能力
  - validate_capabilities: 验证能力集的有效性
  - combine_capabilities: 组合多个能力
  - get_capability_list: 获取能力名称列表
  - get_capability_descriptions: 获取能力描述列表

能力分层：
  - 模型能力（ModelCapability）：PREDICT_PROBA（违约概率）、PREDICT_CLASS（分类标签）、
    PREDICT_LOG_ODDS（原始对数几率）、SHAP（SHAP 解释）、SHAP_TREE（SHAP 树解释）、
    SHAP_KERNEL（SHAP 核解释）、FEATURE_IMPORTANCE（特征重要性）、BATCH_PREDICT（批量预测）
  - 评分卡能力（ScorecardCapability）：SCORECARD_WOE（WOE 转换）、SCORECARD_LOGIT（对数几率）、
    SCORECARD_SCORE（评分卡分数）、SCORECARD_EXPORT（评分卡导出）

依赖关系：
  - 模型能力：PREDICT_CLASS 依赖 PREDICT_PROBA
  - 评分卡能力：SCORECARD_SCORE 依赖 SCORECARD_LOGIT，SCORECARD_LOGIT 依赖 SCORECARD_WOE

使用示例：
    from datamind.core.scoring.capability import (
        ModelCapability, ScorecardCapability, infer_model_capabilities
    )

    class MyAdapter(BaseModelAdapter):
        SUPPORTED_CAPABILITIES = (
            ModelCapability.PREDICT_CLASS |
            ModelCapability.BATCH_PREDICT
        )

        def __init__(self, model):
            super().__init__(model)
            self.capabilities = infer_model_capabilities(self)
"""

from enum import IntFlag, auto
from typing import List, Dict, Set, Any


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

    # 预测能力
    PREDICT_PROBA = auto()
    PREDICT_CLASS = auto()
    PREDICT_LOG_ODDS = auto()

    # 解释能力
    SHAP = auto()
    SHAP_TREE = auto()
    SHAP_KERNEL = auto()
    FEATURE_IMPORTANCE = auto()

    # 工程能力
    BATCH_PREDICT = auto()


class ScorecardCapability(IntFlag):
    """评分卡能力枚举

    描述评分卡的各层能力。

    属性:
        NONE: 无能力
        SCORECARD_WOE: WOE 转换
        SCORECARD_LOGIT: 对数几率
        SCORECARD_SCORE: 评分卡分数
        SCORECARD_EXPORT: 评分卡导出
    """
    NONE = 0

    SCORECARD_WOE = auto()
    SCORECARD_LOGIT = auto()
    SCORECARD_SCORE = auto()
    SCORECARD_EXPORT = auto()


# ==================== 模型能力依赖关系 ====================

_MODEL_CAPABILITY_DEPENDENCIES: Dict[ModelCapability, Set[ModelCapability]] = {
    ModelCapability.PREDICT_LOG_ODDS: {
        ModelCapability.PREDICT_PROBA
    },
    ModelCapability.PREDICT_CLASS: {
        ModelCapability.PREDICT_PROBA
    },
    ModelCapability.SHAP_TREE: {
        ModelCapability.SHAP
    },
    ModelCapability.SHAP_KERNEL: {
        ModelCapability.SHAP
    },
}


# ==================== 评分卡能力依赖关系 ====================

_SCORECARD_CAPABILITY_DEPENDENCIES: Dict[ScorecardCapability, Set[ScorecardCapability]] = {
    ScorecardCapability.SCORECARD_LOGIT: {
        ScorecardCapability.SCORECARD_WOE
    },
    ScorecardCapability.SCORECARD_SCORE: {
        ScorecardCapability.SCORECARD_LOGIT
    },
    ScorecardCapability.SCORECARD_EXPORT: {
        ScorecardCapability.SCORECARD_SCORE
    },
}


# ==================== 能力名称和描述映射 ====================

_MODEL_CAPABILITY_NAMES: Dict[ModelCapability, str] = {
    ModelCapability.PREDICT_PROBA: "PREDICT_PROBA",
    ModelCapability.PREDICT_CLASS: "PREDICT_CLASS",
    ModelCapability.PREDICT_LOG_ODDS: "PREDICT_LOG_ODDS",
    ModelCapability.SHAP: "SHAP",
    ModelCapability.SHAP_TREE: "SHAP_TREE",
    ModelCapability.SHAP_KERNEL: "SHAP_KERNEL",
    ModelCapability.FEATURE_IMPORTANCE: "FEATURE_IMPORTANCE",
    ModelCapability.BATCH_PREDICT: "BATCH_PREDICT",
}

_MODEL_CAPABILITY_DESCRIPTIONS: Dict[ModelCapability, str] = {
    ModelCapability.PREDICT_PROBA: "违约概率",
    ModelCapability.PREDICT_CLASS: "分类标签",
    ModelCapability.PREDICT_LOG_ODDS: "原始对数几率",
    ModelCapability.SHAP: "SHAP 解释",
    ModelCapability.SHAP_TREE: "SHAP 树解释",
    ModelCapability.SHAP_KERNEL: "SHAP 核解释",
    ModelCapability.FEATURE_IMPORTANCE: "特征重要性",
    ModelCapability.BATCH_PREDICT: "批量预测",
}

_SCORECARD_CAPABILITY_NAMES: Dict[ScorecardCapability, str] = {
    ScorecardCapability.SCORECARD_WOE: "SCORECARD_WOE",
    ScorecardCapability.SCORECARD_LOGIT: "SCORECARD_LOGIT",
    ScorecardCapability.SCORECARD_SCORE: "SCORECARD_SCORE",
    ScorecardCapability.SCORECARD_EXPORT: "SCORECARD_EXPORT",
}

_SCORECARD_CAPABILITY_DESCRIPTIONS: Dict[ScorecardCapability, str] = {
    ScorecardCapability.SCORECARD_WOE: "WOE 转换",
    ScorecardCapability.SCORECARD_LOGIT: "对数几率",
    ScorecardCapability.SCORECARD_SCORE: "评分卡分数",
    ScorecardCapability.SCORECARD_EXPORT: "评分卡导出",
}

# 所有模型能力的列表
ALL_MODEL_CAPABILITIES: List[ModelCapability] = [
    ModelCapability.PREDICT_PROBA,
    ModelCapability.PREDICT_CLASS,
    ModelCapability.PREDICT_LOG_ODDS,
    ModelCapability.SHAP,
    ModelCapability.SHAP_TREE,
    ModelCapability.SHAP_KERNEL,
    ModelCapability.FEATURE_IMPORTANCE,
    ModelCapability.BATCH_PREDICT,
]

# 所有评分卡能力的列表
ALL_SCORECARD_CAPABILITIES: List[ScorecardCapability] = [
    ScorecardCapability.SCORECARD_WOE,
    ScorecardCapability.SCORECARD_LOGIT,
    ScorecardCapability.SCORECARD_SCORE,
    ScorecardCapability.SCORECARD_EXPORT,
]

# 必需能力
_REQUIRED_MODEL_CAPABILITIES: Set[ModelCapability] = {
    ModelCapability.PREDICT_PROBA,
}


# ==================== 核心推断函数 ====================

def expand_model_capabilities(caps: ModelCapability) -> ModelCapability:
    """
    根据依赖关系自动补全模型能力

    参数:
        caps: 原始能力集

    返回:
        补全后的能力集
    """
    result = caps
    changed = True

    while changed:
        changed = False
        for cap, deps in _MODEL_CAPABILITY_DEPENDENCIES.items():
            if result & cap:
                deps_mask = ModelCapability.NONE
                for dep in deps:
                    deps_mask |= dep

                if not (result & deps_mask):
                    result |= deps_mask
                    changed = True

    return result


def expand_scorecard_capabilities(caps: ScorecardCapability) -> ScorecardCapability:
    """
    根据依赖关系自动补全评分卡能力

    参数:
        caps: 原始能力集

    返回:
        补全后的能力集
    """
    result = caps
    changed = True

    while changed:
        changed = False
        for cap, deps in _SCORECARD_CAPABILITY_DEPENDENCIES.items():
            if result & cap:
                deps_mask = ScorecardCapability.NONE
                for dep in deps:
                    deps_mask |= dep

                if not (result & deps_mask):
                    result |= deps_mask
                    changed = True

    return result


def infer_model_capabilities(adapter) -> ModelCapability:
    """
    根据适配器声明推断模型能力集

    推断规则：
        - 强制要求实现 predict_proba
        - 优先使用适配器声明的 SUPPORTED_CAPABILITIES
        - 根据方法存在性自动推断
        - 自动补全依赖关系

    参数:
        adapter: 模型适配器实例

    返回:
        ModelCapability 位掩码

    异常:
        RuntimeError: 缺少必需能力 PREDICT_PROBA
        TypeError: SUPPORTED_CAPABILITIES 类型错误
    """
    caps = ModelCapability.NONE

    # 强制要求实现概率预测
    if not callable(getattr(adapter, "predict_proba", None)):
        raise RuntimeError("模型适配器必须实现 predict_proba 方法")

    caps |= ModelCapability.PREDICT_PROBA

    # 优先使用适配器声明
    declared = getattr(adapter, "SUPPORTED_CAPABILITIES", None)

    if declared is not None:
        if not isinstance(declared, ModelCapability):
            raise TypeError(
                f"SUPPORTED_CAPABILITIES 必须是 ModelCapability 类型，当前: {type(declared)}"
            )
        caps |= declared

    # 自动推断对数几率能力
    if callable(getattr(adapter, "decision_function", None)):
        caps |= ModelCapability.PREDICT_LOG_ODDS

    # 自动推断分类能力
    if callable(getattr(adapter, "predict_class", None)):
        caps |= ModelCapability.PREDICT_CLASS

    # 自动推断解释能力
    if callable(getattr(adapter, "get_shap_values", None)):
        caps |= ModelCapability.SHAP

    if callable(getattr(adapter, "get_shap_tree", None)):
        caps |= ModelCapability.SHAP_TREE

    if callable(getattr(adapter, "get_shap_kernel", None)):
        caps |= ModelCapability.SHAP_KERNEL

    if callable(getattr(adapter, "get_feature_importance", None)):
        caps |= ModelCapability.FEATURE_IMPORTANCE

    # 自动推断批量预测能力
    if callable(getattr(adapter, "predict_proba_batch", None)):
        caps |= ModelCapability.BATCH_PREDICT

    # 自动补全依赖关系
    caps = expand_model_capabilities(caps)

    return caps


def infer_scorecard_capabilities(engine) -> ScorecardCapability:
    """
    根据评分卡引擎推断评分卡能力集

    参数:
        engine: 评分卡引擎实例

    返回:
        ScorecardCapability 位掩码
    """
    caps = ScorecardCapability.NONE

    # WOE 转换能力
    if hasattr(engine, "woe_transform") or hasattr(engine, "woe"):
        caps |= ScorecardCapability.SCORECARD_WOE

    # 对数几率输出能力
    if hasattr(engine, "decision_function") or hasattr(engine, "logit"):
        caps |= ScorecardCapability.SCORECARD_LOGIT

    # 评分卡分数输出能力
    if hasattr(engine, "score"):
        caps |= ScorecardCapability.SCORECARD_SCORE

    # 评分卡导出能力
    if hasattr(engine, "export"):
        caps |= ScorecardCapability.SCORECARD_EXPORT

    # 自动补全依赖关系
    caps = expand_scorecard_capabilities(caps)

    return caps


def validate_model_capabilities(caps: ModelCapability) -> List[str]:
    """
    验证模型能力集的有效性

    参数:
        caps: 能力集（位掩码）

    返回:
        错误信息列表，空列表表示验证通过
    """
    errors = []

    # 检查必需能力
    for required in _REQUIRED_MODEL_CAPABILITIES:
        if not (caps & required):
            errors.append(f"缺少必需能力: {_MODEL_CAPABILITY_NAMES.get(required, str(required))}")

    # 检查依赖关系
    for cap, deps in _MODEL_CAPABILITY_DEPENDENCIES.items():
        if caps & cap:
            missing = []
            for dep in deps:
                if not (caps & dep):
                    missing.append(dep)

            if missing:
                missing_names = [_MODEL_CAPABILITY_NAMES.get(d, str(d)) for d in missing]
                errors.append(
                    f"能力 {_MODEL_CAPABILITY_NAMES.get(cap, str(cap))} 缺少依赖: {missing_names}"
                )

    return errors


def validate_scorecard_capabilities(caps: ScorecardCapability) -> List[str]:
    """
    验证评分卡能力集的有效性

    参数:
        caps: 能力集（位掩码）

    返回:
        错误信息列表，空列表表示验证通过
    """
    errors = []

    for cap, deps in _SCORECARD_CAPABILITY_DEPENDENCIES.items():
        if caps & cap:
            missing = []
            for dep in deps:
                if not (caps & dep):
                    missing.append(dep)

            if missing:
                missing_names = [_SCORECARD_CAPABILITY_NAMES.get(d, str(d)) for d in missing]
                errors.append(
                    f"能力 {_SCORECARD_CAPABILITY_NAMES.get(cap, str(cap))} 缺少依赖: {missing_names}"
                )

    return errors


# ==================== 能力检查函数 ====================

def has_model_capability(caps: ModelCapability, capability: ModelCapability) -> bool:
    """检查模型是否包含指定能力"""
    return bool(caps & capability)


def has_scorecard_capability(caps: ScorecardCapability, capability: ScorecardCapability) -> bool:
    """检查评分卡是否包含指定能力"""
    return bool(caps & capability)


def has_all_model_capabilities(caps: ModelCapability, required: ModelCapability) -> bool:
    """检查模型是否包含所有指定能力"""
    return (caps & required) == required


def has_all_scorecard_capabilities(caps: ScorecardCapability, required: ScorecardCapability) -> bool:
    """检查评分卡是否包含所有指定能力"""
    return (caps & required) == required


def has_any_model_capability(caps: ModelCapability, capabilities: ModelCapability) -> bool:
    """检查模型是否包含任意一个指定能力"""
    return bool(caps & capabilities)


def has_any_scorecard_capability(caps: ScorecardCapability, capabilities: ScorecardCapability) -> bool:
    """检查评分卡是否包含任意一个指定能力"""
    return bool(caps & capabilities)


def combine_model_capabilities(capabilities: List[ModelCapability]) -> ModelCapability:
    """组合多个模型能力"""
    result = ModelCapability.NONE
    for cap in capabilities:
        result |= cap
    return result


def combine_scorecard_capabilities(capabilities: List[ScorecardCapability]) -> ScorecardCapability:
    """组合多个评分卡能力"""
    result = ScorecardCapability.NONE
    for cap in capabilities:
        result |= cap
    return result


# ==================== 序列化和展示函数 ====================

def get_model_capability_list(caps: ModelCapability) -> List[str]:
    """获取模型能力名称列表"""
    result: List[str] = []
    for cap in ALL_MODEL_CAPABILITIES:
        if caps & cap:
            result.append(_MODEL_CAPABILITY_NAMES[cap])
    return result


def get_scorecard_capability_list(caps: ScorecardCapability) -> List[str]:
    """获取评分卡能力名称列表"""
    result: List[str] = []
    for cap in ALL_SCORECARD_CAPABILITIES:
        if caps & cap:
            result.append(_SCORECARD_CAPABILITY_NAMES[cap])
    return result


def get_model_capability_descriptions(caps: ModelCapability) -> List[Dict[str, str]]:
    """获取模型能力描述列表"""
    result: List[Dict[str, str]] = []
    for cap in ALL_MODEL_CAPABILITIES:
        if caps & cap:
            result.append({
                "name": _MODEL_CAPABILITY_NAMES[cap],
                "description": _MODEL_CAPABILITY_DESCRIPTIONS.get(cap, _MODEL_CAPABILITY_NAMES[cap])
            })
    return result


def get_scorecard_capability_descriptions(caps: ScorecardCapability) -> List[Dict[str, str]]:
    """获取评分卡能力描述列表"""
    result: List[Dict[str, str]] = []
    for cap in ALL_SCORECARD_CAPABILITIES:
        if caps & cap:
            result.append({
                "name": _SCORECARD_CAPABILITY_NAMES[cap],
                "description": _SCORECARD_CAPABILITY_DESCRIPTIONS.get(cap, _SCORECARD_CAPABILITY_NAMES[cap])
            })
    return result


def get_model_capability_summary(caps: ModelCapability) -> Dict[str, Any]:
    """获取模型能力摘要"""
    return {
        "names": get_model_capability_list(caps),
        "count": len(get_model_capability_list(caps)),
        "validation_errors": validate_model_capabilities(caps)
    }


def get_scorecard_capability_summary(caps: ScorecardCapability) -> Dict[str, Any]:
    """获取评分卡能力摘要"""
    return {
        "names": get_scorecard_capability_list(caps),
        "count": len(get_scorecard_capability_list(caps)),
        "validation_errors": validate_scorecard_capabilities(caps)
    }


__all__ = [
    'ModelCapability',
    'ScorecardCapability',
    'ALL_MODEL_CAPABILITIES',
    'ALL_SCORECARD_CAPABILITIES',
    'infer_model_capabilities',
    'infer_scorecard_capabilities',
    'expand_model_capabilities',
    'expand_scorecard_capabilities',
    'validate_model_capabilities',
    'validate_scorecard_capabilities',
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