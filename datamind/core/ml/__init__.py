# Datamind/datamind/core/ml/__init__.py

"""机器学习模块

提供模型注册、加载、推理等核心功能。

模块组成：
  - model_registry: 模型注册中心，负责模型的注册、版本管理、状态管理
  - model_loader: 模型加载器，负责模型的动态加载、卸载、缓存管理
  - inference: 推理引擎，提供统一的评分卡和反欺诈模型推理接口
  - exceptions: 异常定义，提供机器学习相关的异常类

功能特性：
  - 多框架支持：sklearn、xgboost、lightgbm、torch、tensorflow、onnx、catboost
  - 模型版本管理：支持模型版本控制和历史追溯
  - 生产环境管理：支持模型激活/停用、生产模型切换
  - A/B测试支持：模型分组和流量分配
  - 完整审计：记录所有模型操作日志
"""

from datamind.core.ml.model_registry import model_registry
from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.inference import inference_engine
from datamind.core.ml.exceptions import (
    ModelException,
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelLoadException,
    ModelInferenceException
)

__all__ = [
    'model_registry',
    'model_loader',
    'inference_engine',
    'ModelException',
    'ModelNotFoundException',
    'ModelAlreadyExistsException',
    'ModelValidationException',
    'ModelLoadException',
    'ModelInferenceException',
]