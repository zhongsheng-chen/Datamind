# datamind/core/ml/model/__init__.py
"""模型管理模块

提供模型的加载、注册和推理路由功能。

模块组成：
  - loader: 模型加载器，从 BentoML 加载模型到内存
  - registry: 模型注册中心，管理模型元数据和生命周期
  - inference: 推理引擎，根据模型类型分发到对应的预测器

功能特性：
  - 多框架支持：sklearn、xgboost、lightgbm、torch、tensorflow、onnx、catboost
  - 模型版本管理：支持模型版本控制和历史追溯
  - 生产环境管理：支持模型激活/停用、生产模型切换
  - 完整审计：记录所有模型操作到版本历史表
  - 链路追踪：完整的 span 追踪
"""

from .loader import ModelLoader, get_model_loader
from .registry import ModelRegistry, get_model_registry
from datamind.core.ml.model.inference import InferenceEngine, get_inference_engine

__all__ = [
    'ModelLoader',
    'get_model_loader',
    'ModelRegistry',
    'get_model_registry',
    'InferenceEngine',
    'get_inference_engine',
]