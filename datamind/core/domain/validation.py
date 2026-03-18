# Datamind/datamind/core/domain/validation.py

"""框架-模型兼容性验证

提供框架和模型类型之间的兼容性验证功能。
这些规则是领域层的核心业务规则，应当保持只读和稳定。

如果需要动态扩展兼容性规则，应当通过 SystemConfig 配置表实现，
而不是直接修改此模块的常量。
"""

from typing import Dict, Set, List
from datamind.core.domain.enums import Framework, ModelType


FRAMEWORK_MODEL_COMPATIBILITY: Dict[Framework, Set[ModelType]] = {
    # Scikit-learn 框架支持的模型类型
    Framework.SKLEARN: {
        ModelType.DECISION_TREE,
        ModelType.RANDOM_FOREST,
        ModelType.LOGISTIC_REGRESSION
    },

    # XGBoost 原生框架支持的模型类型
    Framework.XGBOOST: {
        ModelType.XGBOOST
    },

    # LightGBM 原生框架支持的模型类型
    Framework.LIGHTGBM: {
        ModelType.LIGHTGBM
    },

    # CatBoost 原生框架支持的模型类型
    Framework.CATBOOST: {
        ModelType.CATBOOST
    },

    # PyTorch 框架支持的模型类型
    Framework.TORCH: {
        ModelType.NEURAL_NETWORK,
        ModelType.LOGISTIC_REGRESSION
    },

    # TensorFlow 框架支持的模型类型
    Framework.TENSORFLOW: {
        ModelType.NEURAL_NETWORK,
        ModelType.LOGISTIC_REGRESSION
    },

    # ONNX 运行时支持的模型类型
    Framework.ONNX: {
        ModelType.DECISION_TREE,
        ModelType.RANDOM_FOREST,
        ModelType.XGBOOST,
        ModelType.LIGHTGBM,
        ModelType.CATBOOST,
        ModelType.LOGISTIC_REGRESSION,
        ModelType.NEURAL_NETWORK
    }
}


def is_compatible(framework: Framework, model_type: ModelType) -> bool:
    """检查框架和模型类型是否兼容

    根据领域规则验证给定的框架是否支持指定的模型类型。

    参数:
        framework: 机器学习框架
        model_type: 模型类型

    返回:
        True 如果兼容，否则 False

    示例:
        >>> is_compatible(Framework.XGBOOST, ModelType.XGBOOST)
        True
        >>> is_compatible(Framework.XGBOOST, ModelType.LIGHTGBM)
        False
    """
    return model_type in FRAMEWORK_MODEL_COMPATIBILITY.get(framework, set())


def get_supported_models(framework: Framework) -> List[ModelType]:
    """获取指定框架支持的模型类型列表

    参数:
        framework: 机器学习框架

    返回:
        支持的模型类型列表

    示例:
        >>> models = get_supported_models(Framework.TORCH)
        >>> [m.value for m in models]
        ['neural_network', 'logistic_regression']
    """
    return list(FRAMEWORK_MODEL_COMPATIBILITY.get(framework, set()))


def get_supported_frameworks(model_type: ModelType) -> List[Framework]:
    """获取指定模型类型支持的框架列表

    参数:
        model_type: 模型类型

    返回:
        支持的框架列表

    示例:
        >>> frameworks = get_supported_frameworks(ModelType.NEURAL_NETWORK)
        >>> [f.value for f in frameworks]
        ['torch', 'tensorflow', 'onnx']
    """
    return [
        framework
        for framework, models in FRAMEWORK_MODEL_COMPATIBILITY.items()
        if model_type in models
    ]


def validate_or_raise(framework: Framework, model_type: ModelType):
    """验证兼容性，不兼容时抛出异常

    在模型创建或部署前调用此方法，确保框架和模型类型的组合是有效的。

    参数:
        framework: 机器学习框架
        model_type: 模型类型

    抛出:
        ValueError: 如果框架和模型类型不兼容

    示例:
        >>> validate_or_raise(Framework.SKLEARN, ModelType.RANDOM_FOREST)  # 正常
        >>> validate_or_raise(Framework.SKLEARN, ModelType.XGBOOST)  # 抛出异常
        Traceback (most recent call last):
        ValueError: 框架 'sklearn' 不支持模型类型 'xgboost'...
    """
    if not is_compatible(framework, model_type):
        supported = get_supported_models(framework)
        supported_names = [m.value for m in supported]
        raise ValueError(
            f"框架 '{framework.value}' 不支持模型类型 '{model_type.value}'。\n"
            f"支持的模型类型: {supported_names}"
        )