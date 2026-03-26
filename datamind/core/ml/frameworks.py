# datamind/core/ml/frameworks.py

"""机器学习框架配置

集中管理 BentoML 框架映射和签名配置，避免循环导入。

核心功能：
  - get_bentoml_backend: 获取框架对应的 BentoML 后端
  - get_framework_signatures: 获取框架对应的签名配置
  - is_framework_supported: 检查框架是否支持
  - get_supported_frameworks: 获取支持的框架列表

特性：
  - 单一数据源：所有框架配置集中定义
  - 易于扩展：添加新框架只需修改映射表
  - 类型安全：使用枚举和类型提示
"""

import bentoml
from typing import List, Dict, Any


# BentoML 框架映射
FRAMEWORK_TO_BENTOML = {
    'sklearn': bentoml.sklearn,
    'xgboost': bentoml.xgboost,
    'lightgbm': bentoml.lightgbm,
    'catboost': bentoml.catboost,
    'torch': bentoml.pytorch,
    'pytorch': bentoml.pytorch,
    'tensorflow': bentoml.tensorflow,
    'onnx': bentoml.onnx,
}

# BentoML 框架的签名配置
FRAMEWORK_SIGNATURES = {
    'sklearn': {
        "predict": {"batchable": True, "batch_dim": 0},
        "predict_proba": {"batchable": True, "batch_dim": 0}
    },
    'xgboost': {"predict": {"batchable": True}},
    'lightgbm': {"predict": {"batchable": True}},
    'catboost': {"predict": {"batchable": True}},
    'torch': {"predict": {"batchable": True}},
    'pytorch': {"predict": {"batchable": True}},
    'tensorflow': {"predict": {"batchable": True}},
    'onnx': {"predict": {"batchable": True}},
}

# 支持的框架列表（单一数据源）
SUPPORTED_FRAMEWORKS = list(FRAMEWORK_TO_BENTOML.keys())


def get_bentoml_backend(framework: str):
    """
    获取框架对应的 BentoML 后端

    参数:
        framework: 框架名称

    返回:
        BentoML 后端模块对象

    异常:
        ValueError: 不支持的框架
    """
    framework_lower = framework.lower()
    backend = FRAMEWORK_TO_BENTOML.get(framework_lower)
    if backend is None:
        raise ValueError(
            f"不支持的框架: {framework}. 支持的框架: {SUPPORTED_FRAMEWORKS}"
        )
    return backend


def get_framework_signatures(framework: str) -> Dict[str, Any]:
    """
    获取框架对应的签名配置

    参数:
        framework: 框架名称

    返回:
        签名配置字典
    """
    framework_lower = framework.lower()
    return FRAMEWORK_SIGNATURES.get(framework_lower, {"predict": {"batchable": True}})


def is_framework_supported(framework: str) -> bool:
    """
    检查框架是否支持

    参数:
        framework: 框架名称

    返回:
        是否支持
    """
    return framework.lower() in SUPPORTED_FRAMEWORKS


def get_supported_frameworks() -> List[str]:
    """
    获取支持的框架列表

    返回:
        支持的框架名称列表
    """
    return SUPPORTED_FRAMEWORKS.copy()