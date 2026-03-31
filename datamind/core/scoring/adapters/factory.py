# datamind/core/scoring/adapters/factory.py

"""模型适配器工厂

核心功能：
  - get_adapter: 自动识别模型并返回适配器
  - register_adapter: 注册新的适配器（支持扩展）
  - unregister_adapter: 注销适配器
  - is_supported: 检查模型是否支持
  - get_supported_frameworks: 获取支持的框架列表
  - clear_registry: 清空注册表（测试用）

特性：
  - 注册机制：新增框架无需修改工厂代码
  - 权重匹配：支持关键字权重，自动识别更精准
  - 优先级控制：多匹配时按优先级选择
  - 显式框架指定：推荐生产环境使用
"""

from typing import List, Optional, Type, Dict, Any
from collections import Counter

from datamind.core.logging.manager import LogManager
from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.common.frameworks import get_supported_frameworks as get_frameworks_list

_ADAPTER_REGISTRY: List[Dict[str, Any]] = []

# 获取日志器
_log_manager = LogManager()
_logger = _log_manager.app_logger


def register_adapter(
    adapter_cls: Type[BaseModelAdapter],
    keywords: List[str],
    priority: int = 100,
    frameworks: Optional[List[str]] = None
) -> None:
    """
    注册适配器

    参数:
        adapter_cls: 适配器类
        keywords: 用于识别模型的关键字列表（可重复以增加权重）
        priority: 优先级（数字越小优先级越高，默认100）
        frameworks: 显式支持的框架列表
    """
    _ADAPTER_REGISTRY.append({
        "class": adapter_cls,
        "keywords": [k.lower() for k in keywords],
        "priority": priority,
        "frameworks": [f.lower() for f in (frameworks or [])]
    })
    _ADAPTER_REGISTRY.sort(key=lambda x: x["priority"])
    if _logger:
        _logger.debug(f"注册适配器: {adapter_cls.__name__}, 优先级: {priority}, 关键字数: {len(keywords)}")


def unregister_adapter(adapter_cls: Type[BaseModelAdapter]) -> bool:
    """
    注销适配器

    参数:
        adapter_cls: 要注销的适配器类

    返回:
        True 表示注销成功，False 表示未找到
    """
    for i, item in enumerate(_ADAPTER_REGISTRY):
        if item["class"] == adapter_cls:
            _ADAPTER_REGISTRY.pop(i)
            if _logger:
                _logger.debug(f"注销适配器: {adapter_cls.__name__}")
            return True
    return False


def get_adapter(
    model,
    framework: Optional[str] = None,
    feature_names: Optional[List[str]] = None
) -> BaseModelAdapter:
    """
    获取模型适配器

    参数:
        model: 训练好的模型
        framework: 框架名称（可选，推荐显式指定）
        feature_names: 特征名称列表（可选）

    返回:
        BaseModelAdapter 实例

    异常:
        ValueError: 不支持的模型类型
    """
    # 显式指定框架（优先）
    if framework:
        for item in _ADAPTER_REGISTRY:
            if framework.lower() in item["frameworks"]:
                if _logger:
                    _logger.debug(f"使用显式框架: {framework}")
                return item["class"](model, feature_names)
        raise ValueError(f"不支持的框架: {framework}")

    # 自动识别
    module = model.__class__.__module__.lower()
    name = model.__class__.__name__.lower()

    if _logger:
        _logger.debug(f"识别模型: {module}.{name}")

    # 计算匹配分数
    best_score = -1
    best_adapter = None

    for item in _ADAPTER_REGISTRY:
        # 计算关键字匹配分数
        score = 0
        for keyword in item["keywords"]:
            if keyword in module or keyword in name:
                score += 1

        if score > best_score:
            best_score = score
            best_adapter = item["class"]
            if _logger:
                _logger.debug(f"候选适配器: {best_adapter.__name__}, 分数: {score}")

    if best_adapter:
        if _logger:
            _logger.debug(f"选定适配器: {best_adapter.__name__}, 分数: {best_score}")
        return best_adapter(model, feature_names)

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
    frameworks = set()
    for item in _ADAPTER_REGISTRY:
        frameworks.update(item["frameworks"])
    return sorted(frameworks) or get_frameworks_list()


def clear_registry() -> None:
    """清空注册表（主要用于测试）"""
    _ADAPTER_REGISTRY.clear()
    if _logger:
        _logger.debug("已清空注册表")


def _register_builtin_adapters() -> None:
    """注册内置适配器（通过重复关键字实现权重）"""
    from .sklearn import SklearnAdapter
    from .xgboost import XGBoostAdapter
    from .lightgbm import LightGBMAdapter
    from .catboost import CatBoostAdapter
    from .torch import TorchAdapter
    from .tensorflow import TensorFlowAdapter
    from .onnx import ONNXAdapter

    # 通过重复关键字增加权重（出现次数越多，匹配优先级越高）
    builtin_adapters = [
        (SklearnAdapter, ["sklearn"] * 10, 10, ["sklearn"]),
        (XGBoostAdapter, ["xgboost"] * 10, 10, ["xgboost"]),
        (LightGBMAdapter, ["lightgbm"] * 10, 20, ["lightgbm"]),
        (CatBoostAdapter, ["catboost"] * 10, 20, ["catboost"]),
        (TorchAdapter, ["torch"] * 10 + ["pytorch"] * 8, 30, ["torch"]),
        (TensorFlowAdapter, ["tensorflow"] * 10 + ["keras"] * 6 + ["tf"] * 4, 30, ["tensorflow"]),
        (ONNXAdapter, ["onnx"] * 10 + ["onnxruntime"] * 6, 40, ["onnx"]),
    ]

    for adapter_cls, keywords, priority, frameworks in builtin_adapters:
        register_adapter(adapter_cls, keywords=keywords, priority=priority, frameworks=frameworks)


# 初始化内置适配器
_register_builtin_adapters()