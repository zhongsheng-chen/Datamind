# datamind/core/ml/common/__init__.py
"""通用基础模块

提供所有机器学习模块共用的基础功能。

模块组成：
  - exceptions: 异常定义
  - frameworks: 框架配置
  - cache: 缓存管理
  - adapters: 框架适配器

功能特性：
  - 统一异常体系：所有 ML 相关异常统一管理
  - 框架配置中心：集中管理支持的框架列表
  - 缓存管理：提供 LRU 缓存和缓存键生成
  - 框架适配器：为不同框架提供统一接口
"""

from .exceptions import (
    ModelException,
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelLoadException,
    ModelInferenceException,
    UnsupportedFrameworkException,
    UnsupportedModelTypeException,
    ModelFileException
)

from .frameworks import (
    is_framework_supported,
    get_supported_frameworks,
    get_bentoml_backend,
    get_framework_signatures
)

from .cache import LRUCache, CacheKeyGenerator

__all__ = [
    'ModelException',
    'ModelNotFoundException',
    'ModelAlreadyExistsException',
    'ModelValidationException',
    'ModelLoadException',
    'ModelInferenceException',
    'UnsupportedFrameworkException',
    'UnsupportedModelTypeException',
    'ModelFileException',
    'is_framework_supported',
    'get_supported_frameworks',
    'get_bentoml_backend',
    'get_framework_signatures',
    'LRUCache',
    'CacheKeyGenerator',
]