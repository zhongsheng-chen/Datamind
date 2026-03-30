# datamind/core/ml/capability/enum.py
"""模型能力定义

定义模型支持的各种能力，实现模型类型与能力的解耦。

核心功能：
  - 能力声明：每个模型声明自己支持的能力
  - 能力检查：运行时判断模型是否支持特定能力
  - 能力映射：根据框架和模型类型自动生成能力集
  - 能力描述：提供能力的中文说明（用于 API 响应）

设计原则：
  - 模型是什么不重要，模型能干什么才重要
  - 新模型只需声明能力，无需修改核心逻辑
  - Pipeline 根据能力自动适配，不再依赖 model_type 判断

能力分类：
  - 基础能力：PREDICT_PROBA、PREDICT_SCORE、PREDICT_CLASS
  - 评分卡能力：SCORECARD、FEATURE_SCORES
  - 解释能力：SHAP、FEATURE_IMPORTANCE
  - 高级能力：REASON_CODE、EXPORT_SCORECARD
  - 实验能力：CHALLENGER

使用示例：
  >>> from datamind.core.ml.capability import ModelCapability, has_capability
  >>>
  >>> caps = model.get_capabilities()
  >>> if has_capability(caps, ModelCapability.SCORECARD):
  >>>     # 评分卡模型：返回特征分
  >>>     result = scorecard_pipeline.run(model, request)
  >>> elif has_capability(caps, ModelCapability.SHAP):
  >>>     # 树模型：返回 SHAP 解释
  >>>     result = shap_pipeline.run(model, request)
"""

from enum import IntFlag, auto
from typing import List, Dict, Optional


class ModelCapability(IntFlag):
    """模型能力枚举

    使用 IntFlag 支持位运算，可高效组合和判断多个能力。

    属性:
        NONE: 无能力
        PREDICT_PROBA: 输出违约概率
        PREDICT_SCORE: 输出信用评分
        PREDICT_CLASS: 输出分类标签（0/1）
        SCORECARD: 支持评分卡体系
        FEATURE_SCORES: 支持特征分
        SHAP: 支持 SHAP 值解释
        FEATURE_IMPORTANCE: 支持全局特征重要性
        REASON_CODE: 支持拒绝原因
        EXPORT_SCORECARD: 支持导出评分卡
        CHALLENGER: 可作为陪跑模型参与 A/B 测试
    """
    NONE = 0
    PREDICT_PROBA = auto()
    PREDICT_SCORE = auto()
    PREDICT_CLASS = auto()
    SCORECARD = auto()
    FEATURE_SCORES = auto()
    SHAP = auto()
    FEATURE_IMPORTANCE = auto()
    REASON_CODE = auto()
    EXPORT_SCORECARD = auto()
    CHALLENGER = auto()


def get_capabilities_for_lr() -> ModelCapability:
    """逻辑回归（评分卡）能力集

    返回:
        ModelCapability 位掩码，包含 PREDICT_PROBA、PREDICT_SCORE、
        SCORECARD、FEATURE_SCORES、REASON_CODE、EXPORT_SCORECARD
    """
    return (
        ModelCapability.PREDICT_PROBA |
        ModelCapability.PREDICT_SCORE |
        ModelCapability.SCORECARD |
        ModelCapability.FEATURE_SCORES |
        ModelCapability.REASON_CODE |
        ModelCapability.EXPORT_SCORECARD
    )


def get_capabilities_for_tree() -> ModelCapability:
    """树模型能力集

    适用于 XGBoost、LightGBM、CatBoost、随机森林等。

    返回:
        ModelCapability 位掩码，包含 PREDICT_PROBA、PREDICT_CLASS、
        SHAP、FEATURE_IMPORTANCE、CHALLENGER
    """
    return (
        ModelCapability.PREDICT_PROBA |
        ModelCapability.PREDICT_CLASS |
        ModelCapability.SHAP |
        ModelCapability.FEATURE_IMPORTANCE |
        ModelCapability.CHALLENGER
    )


def get_capabilities_for_deep_learning() -> ModelCapability:
    """深度学习模型能力集

    适用于 PyTorch、TensorFlow 等。

    返回:
        ModelCapability 位掩码，包含 PREDICT_PROBA、PREDICT_CLASS
    """
    return (
        ModelCapability.PREDICT_PROBA |
        ModelCapability.PREDICT_CLASS
    )


def get_capabilities_for_onnx() -> ModelCapability:
    """ONNX 模型能力集

    返回:
        ModelCapability 位掩码，包含 PREDICT_PROBA、PREDICT_CLASS
    """
    return (
        ModelCapability.PREDICT_PROBA |
        ModelCapability.PREDICT_CLASS
    )


def get_capabilities_for_sklearn_default() -> ModelCapability:
    """通用 sklearn 模型能力集

    适用于非 LR 的 sklearn 模型。

    返回:
        ModelCapability 位掩码，包含 PREDICT_PROBA、PREDICT_CLASS、
        FEATURE_IMPORTANCE、CHALLENGER
    """
    return (
        ModelCapability.PREDICT_PROBA |
        ModelCapability.PREDICT_CLASS |
        ModelCapability.FEATURE_IMPORTANCE |
        ModelCapability.CHALLENGER
    )


FRAMEWORK_CAPABILITIES = {
    "sklearn": {
        "logistic_regression": get_capabilities_for_lr,
        "decision_tree": get_capabilities_for_tree,
        "random_forest": get_capabilities_for_tree,
        "default": get_capabilities_for_sklearn_default,
    },
    "xgboost": get_capabilities_for_tree,
    "lightgbm": get_capabilities_for_tree,
    "catboost": get_capabilities_for_tree,
    "torch": get_capabilities_for_deep_learning,
    "pytorch": get_capabilities_for_deep_learning,
    "tensorflow": get_capabilities_for_deep_learning,
    "onnx": get_capabilities_for_onnx,
}


def get_capabilities_by_model_type(
    framework: str,
    model_type: Optional[str] = None
) -> ModelCapability:
    """
    根据框架和模型类型获取能力集

    参数:
        framework: 框架名称（sklearn、xgboost、lightgbm等）
        model_type: 模型类型（logistic_regression、xgboost等）

    返回:
        ModelCapability 位掩码

    示例:
        >>> caps = get_capabilities_by_model_type("sklearn", "logistic_regression")
        >>> print(caps & ModelCapability.FEATURE_SCORES)
        True
    """
    caps_config = FRAMEWORK_CAPABILITIES.get(framework.lower())

    if caps_config is None:
        return ModelCapability.PREDICT_PROBA | ModelCapability.PREDICT_CLASS

    if isinstance(caps_config, dict):
        if model_type and model_type in caps_config:
            return caps_config[model_type]()
        return caps_config.get("default", lambda: ModelCapability.PREDICT_PROBA)()

    return caps_config()


def has_capability(caps: ModelCapability, capability: ModelCapability) -> bool:
    """
    检查是否包含指定能力

    参数:
        caps: 能力集（位掩码）
        capability: 要检查的能力

    返回:
        True 表示包含该能力，False 表示不包含

    示例:
        >>> caps = get_capabilities_for_lr()
        >>> has_capability(caps, ModelCapability.FEATURE_SCORES)
        True
        >>> has_capability(caps, ModelCapability.SHAP)
        False
    """
    return bool(caps & capability)


def get_capability_list(caps: ModelCapability) -> List[str]:
    """
    获取能力名称列表（用于序列化）

    参数:
        caps: 能力集（位掩码）

    返回:
        能力名称列表，如 ["PREDICT_PROBA", "SCORECARD", "FEATURE_SCORES"]

    示例:
        >>> caps = get_capabilities_for_lr()
        >>> get_capability_list(caps)
        ['PREDICT_PROBA', 'PREDICT_SCORE', 'SCORECARD', 'FEATURE_SCORES', 'REASON_CODE', 'EXPORT_SCORECARD']
    """
    all_caps = [
        ModelCapability.PREDICT_PROBA,
        ModelCapability.PREDICT_SCORE,
        ModelCapability.PREDICT_CLASS,
        ModelCapability.SCORECARD,
        ModelCapability.FEATURE_SCORES,
        ModelCapability.SHAP,
        ModelCapability.FEATURE_IMPORTANCE,
        ModelCapability.REASON_CODE,
        ModelCapability.EXPORT_SCORECARD,
        ModelCapability.CHALLENGER,
    ]
    return [cap.name for cap in all_caps if caps & cap]


def get_capability_descriptions(caps: ModelCapability) -> List[Dict[str, str]]:
    """
    获取能力描述列表（用于 API 响应）

    参数:
        caps: 能力集（位掩码）

    返回:
        能力描述列表，每项包含 name 和 description

    示例:
        >>> caps = get_capabilities_for_lr()
        >>> get_capability_descriptions(caps)
        [
            {"name": "PREDICT_PROBA", "description": "支持概率输出"},
            {"name": "SCORECARD", "description": "支持评分卡体系"},
            ...
        ]
    """
    descriptions = {
        "PREDICT_PROBA": "支持概率输出",
        "PREDICT_SCORE": "支持信用评分",
        "PREDICT_CLASS": "支持分类标签",
        "SCORECARD": "支持评分卡体系",
        "FEATURE_SCORES": "支持特征分",
        "SHAP": "支持 SHAP 解释",
        "FEATURE_IMPORTANCE": "支持特征重要性",
        "REASON_CODE": "支持拒绝原因",
        "EXPORT_SCORECARD": "支持导出评分卡",
        "CHALLENGER": "可作为陪跑模型",
    }

    result = []
    for cap in [
        ModelCapability.PREDICT_PROBA,
        ModelCapability.PREDICT_SCORE,
        ModelCapability.PREDICT_CLASS,
        ModelCapability.SCORECARD,
        ModelCapability.FEATURE_SCORES,
        ModelCapability.SHAP,
        ModelCapability.FEATURE_IMPORTANCE,
        ModelCapability.REASON_CODE,
        ModelCapability.EXPORT_SCORECARD,
        ModelCapability.CHALLENGER,
    ]:
        if caps & cap:
            result.append({
                "name": cap.name,
                "description": descriptions.get(cap.name, cap.name)
            })
    return result


__all__ = [
    'ModelCapability',
    'get_capabilities_for_lr',
    'get_capabilities_for_tree',
    'get_capabilities_for_deep_learning',
    'get_capabilities_for_onnx',
    'get_capabilities_for_sklearn_default',
    'get_capabilities_by_model_type',
    'has_capability',
    'get_capability_list',
    'get_capability_descriptions',
]