# datamind/core/ml/adapters/factory.py

"""模型适配器工厂

自动识别模型类型并返回对应的适配器实例。

核心功能：
  - get_adapter: 自动识别模型并返回适配器
  - is_supported: 检查模型是否支持
  - get_supported_frameworks: 获取支持的框架列表

特性：
  - 自动识别：根据模型类名和模块名自动识别框架
  - 统一接口：所有模型返回统一的适配器接口
  - 可扩展：新增框架只需在工厂中添加识别逻辑
  - 复用配置：框架列表从 frameworks.py 获取，保持单一数据源

识别规则：
  - sklearn: 模块名或类名包含 "sklearn"
  - xgboost: 模块名或类名包含 "xgboost"
  - lightgbm: 模块名或类名包含 "lightgbm"
  - catboost: 模块名或类名包含 "catboost"
  - pytorch: 模块名或类名包含 "torch" 或 "pytorch"
  - tensorflow: 模块名包含 "tensorflow"、"keras" 或 "tf"
  - onnx: 模块名包含 "onnx" 或 "onnxruntime"

使用示例：
    >>> from datamind.core.ml.adapters.factory import get_adapter
    >>>
    >>> # 自动识别 sklearn 模型
    >>> from sklearn.ensemble import RandomForestClassifier
    >>> model = RandomForestClassifier()
    >>> adapter = get_adapter(model, feature_names=["age", "income"])
    >>> prob = adapter.predict({"age": 35, "income": 50000})
"""

from typing import Any, List, Optional

from datamind.core.logging.debug import debug_print
from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.ml.frameworks import get_supported_frameworks as get_frameworks_list


def get_adapter(model, feature_names: Optional[List[str]] = None) -> BaseModelAdapter:
    """
    自动识别模型并返回对应的适配器

    参数:
        model: 训练好的模型
        feature_names: 特征名称列表（可选，用于保证特征顺序）

    返回:
        BaseModelAdapter 实例

    异常:
        ValueError: 不支持的模型类型
    """
    module = model.__class__.__module__.lower()
    name = model.__class__.__name__.lower()

    debug_print("AdapterFactory", f"识别模型: {module}.{name}")

    # sklearn 系列（包括 pipeline）
    if "sklearn" in module or "sklearn" in name:
        from .sklearn import SklearnAdapter
        return SklearnAdapter(model, feature_names)

    # XGBoost
    if "xgboost" in module or "xgboost" in name:
        from .xgboost import XGBoostAdapter
        return XGBoostAdapter(model, feature_names)

    # LightGBM
    if "lightgbm" in module or "lightgbm" in name:
        from .lightgbm import LightGBMAdapter
        return LightGBMAdapter(model, feature_names)

    # CatBoost
    if "catboost" in module or "catboost" in name:
        from .catboost import CatBoostAdapter
        return CatBoostAdapter(model, feature_names)

    # PyTorch
    if "torch" in module or "pytorch" in name:
        from .torch import TorchAdapter
        return TorchAdapter(model, feature_names)

    # TensorFlow / Keras
    if "tensorflow" in module or "keras" in module or "tf" in module:
        from .tensorflow import TensorFlowAdapter
        return TensorFlowAdapter(model, feature_names)

    # ONNX Runtime
    if "onnx" in module or "onnxruntime" in module:
        from .onnx import ONNXAdapter
        return ONNXAdapter(model, feature_names)

    raise ValueError(f"不支持的模型类型: {module}.{name}")


def is_supported(model) -> bool:
    """
    检查模型是否支持

    参数:
        model: 模型实例

    返回:
        True 表示支持，False 表示不支持
    """
    try:
        get_adapter(model)
        return True
    except ValueError:
        return False


def get_supported_frameworks() -> List[str]:
    """
    获取支持的框架列表

    返回:
        支持的框架名称列表
    """
    return get_frameworks_list()