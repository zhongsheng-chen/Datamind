# datamind/core/scoring/adapters/__init__.py

"""模型适配器模块

为不同机器学习框架提供统一的接口抽象。

模块组成：
  - base: 适配器基类
  - factory: 适配器工厂，自动识别模型类型
  - sklearn: Scikit-learn 模型适配器
  - xgboost: XGBoost 模型适配器
  - lightgbm: LightGBM 模型适配器
  - catboost: CatBoost 模型适配器
  - torch: PyTorch 模型适配器
  - tensorflow: TensorFlow/Keras 模型适配器
  - onnx: ONNX Runtime 模型适配器
"""

from .base import BaseModelAdapter
from .factory import get_adapter, is_supported, get_supported_frameworks

from .sklearn import SklearnAdapter
from .xgboost import XGBoostAdapter
from .lightgbm import LightGBMAdapter
from .catboost import CatBoostAdapter
from .torch import TorchAdapter
from .tensorflow import TensorFlowAdapter
from .onnx import ONNXAdapter

__all__ = [
    'BaseModelAdapter',
    'get_adapter',
    'is_supported',
    'get_supported_frameworks',
    'SklearnAdapter',
    'XGBoostAdapter',
    'LightGBMAdapter',
    'CatBoostAdapter',
    'TorchAdapter',
    'TensorFlowAdapter',
    'ONNXAdapter',
]