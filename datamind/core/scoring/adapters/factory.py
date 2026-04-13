# datamind/core/scoring/adapters/factory.py

"""模型适配器工厂

核心功能：
  - get_adapter: 获取模型适配器（支持显式指定和自动识别）
  - register_adapter: 注册新的适配器（支持扩展）
  - unregister_adapter: 注销适配器
  - is_supported: 检查模型是否支持
  - get_supported_frameworks: 获取支持的框架列表
  - clear_registry: 清空注册表（测试用）

特性：
  - 注册机制：新增框架无需修改工厂代码
  - 权重匹配：支持关键字权重，自动识别更精准
  - 优先级控制：多匹配时按优先级选择
  - 显式框架指定：生产环境推荐使用，避免误识别
  - 防重复注册：同一适配器只注册一次
  - 统一评分：can_handle 与 keywords 统一打分，避免低优先级适配器抢跑
"""

import threading
from typing import List, Optional, Type, Dict, Any, Callable

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.common.frameworks import get_supported_frameworks as get_frameworks_list
from datamind.core.logging import get_logger

_logger = get_logger(__name__)


# ==================== 注册表 ====================

_ADAPTER_REGISTRY: List[Dict[str, Any]] = []
_REGISTRY_LOCK = threading.RLock()
_INIT_LOCK = threading.Lock()
_INITIALIZED = False


# ==================== 懒初始化 ====================

def _ensure_initialized():
    """确保适配器已初始化（懒加载，避免 import 副作用，线程安全）"""
    global _INITIALIZED
    if not _INITIALIZED:
        with _INIT_LOCK:
            if not _INITIALIZED:
                with _REGISTRY_LOCK:
                    _register_builtin_adapters()
                _INITIALIZED = True


# ==================== 辅助函数 ====================

def _get_registry_snapshot() -> List[Dict[str, Any]]:
    """获取注册表的快照（读操作，返回副本）"""
    with _REGISTRY_LOCK:
        return list(_ADAPTER_REGISTRY)


def _unwrap_pipeline(model):
    """解包 Pipeline，获取最终估算器"""
    if hasattr(model, 'steps') and isinstance(model.steps, list) and model.steps:
        if hasattr(model, 'named_steps'):
            return _unwrap_pipeline(model.steps[-1][1])
        return _unwrap_pipeline(model.steps[-1][1])
    return model


def _framework_match(fw: str, adapter_frameworks: List[str]) -> bool:
    """
    框架匹配（支持宽匹配）

    策略：
        1. 精确匹配
        2. 包含关系匹配（如 "torch" 匹配 "pytorch"）
    """
    fw_lower = fw.lower()
    for af in adapter_frameworks:
        af_lower = af.lower()
        if fw_lower == af_lower:
            return True
        if fw_lower in af_lower or af_lower in fw_lower:
            return True
    return False


# ==================== 注册接口 ====================

def register_adapter(
        adapter_cls: Type[BaseModelAdapter],
        keywords: List[str],
        priority: int = 100,
        frameworks: Optional[List[str]] = None,
        can_handle: Optional[Callable] = None,
        weight: int = 1
) -> None:
    """
    注册适配器

    参数:
        adapter_cls: 适配器类
        keywords: 用于识别模型的关键字列表
        priority: 优先级（数字越小优先级越高，默认100）
        frameworks: 显式支持的框架列表
        can_handle: 可选的自定义判断函数，签名: (model) -> bool
        weight: 关键字权重（默认1），用于控制匹配优先级
    """
    if not keywords and not frameworks and can_handle is None:
        raise ValueError("注册适配器必须提供 keywords、frameworks 或 can_handle 其中之一")

    with _REGISTRY_LOCK:
        # 防重复注册
        for item in _ADAPTER_REGISTRY:
            if item["class"] == adapter_cls:
                _logger.debug("适配器已注册，跳过: %s", adapter_cls.__name__)
                return

        record = {
            "class": adapter_cls,
            "keywords": [k.lower() for k in keywords],
            "weight": weight,
            "priority": priority,
            "frameworks": [f.lower() for f in (frameworks or [])],
            "can_handle": can_handle
        }

        _ADAPTER_REGISTRY.append(record)
        _ADAPTER_REGISTRY.sort(key=lambda x: x["priority"])

        _logger.debug(
            "注册适配器: %s, 优先级: %d, 关键字数: %d, 权重: %d, 框架数: %d, 自定义判断: %s",
            adapter_cls.__name__,
            priority,
            len(keywords),
            weight,
            len(record["frameworks"]),
            "有" if can_handle else "无"
        )


def unregister_adapter(adapter_cls: Type[BaseModelAdapter]) -> bool:
    """
    注销适配器

    参数:
        adapter_cls: 要注销的适配器类

    返回:
        True 表示注销成功，False 表示未找到
    """
    with _REGISTRY_LOCK:
        for i, item in enumerate(_ADAPTER_REGISTRY):
            if item["class"] == adapter_cls:
                _ADAPTER_REGISTRY.pop(i)
                _logger.debug("注销适配器: %s", adapter_cls.__name__)
                return True
    return False


# ==================== 获取适配器 ====================

def get_adapter(
        model,
        framework: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
        data_types: Optional[Dict[str, Any]] = None,
) -> BaseModelAdapter:
    """
    获取模型适配器

    优先级：
        - 显式 framework（生产推荐）
        - 统一评分（can_handle + keywords）
        - can_handle 权重 1000，keywords 权重由 weight 参数控制

    参数:
        model: 训练好的模型
        framework: 框架名称（可选，推荐显式指定）
        feature_names: 特征名称列表（可选）
        data_types: 特征数据类型映射（可选）

    返回:
        BaseModelAdapter 实例

    异常:
        ValueError: 不支持的模型类型
    """
    _ensure_initialized()

    # 解包 Pipeline
    model = _unwrap_pipeline(model)

    module = model.__class__.__module__.lower()
    name = model.__class__.__name__.lower()

    registry = _get_registry_snapshot()
    _logger.debug("识别模型: %s.%s", module, name)

    if framework:
        fw = framework.lower()
        candidates = [item for item in registry if _framework_match(fw, item["frameworks"])]
        if not candidates:
            raise ValueError(f"不支持的框架: {framework}")

        best = min(candidates, key=lambda x: x["priority"])
        _logger.info("使用显式框架: %s -> %s", fw, best["class"].__name__)
        return best["class"](model, feature_names, data_types)

    # ---------- 自动匹配 ----------
    best_score = -1
    best_priority = float("inf")
    best_cls = None

    for item in registry:
        score = 0
        kw_score = 0

        # 弱匹配：keyword（权重由 weight 参数控制）
        for kw in item["keywords"]:
            if kw in module or kw in name:
                kw_score += 1

        score += kw_score * item.get("weight", 1)

        # 强匹配：can_handle
        if item["can_handle"] is not None:
            should_check = False

            if kw_score > 0:
                should_check = True
            elif kw_score == 0 and not item["keywords"]:
                should_check = True

            if should_check:
                try:
                    if item["can_handle"](model):
                        score += 1000
                        _logger.debug("can_handle 匹配: %s, 加分 1000", item["class"].__name__)
                except Exception as e:
                    _logger.debug("can_handle 执行失败: %s, %s", item["class"].__name__, e)

        if kw_score > 0:
            _logger.debug("keyword 匹配: %s, 加分 %d (weight=%d)",
                          item["class"].__name__, kw_score, item.get("weight", 1))

        # 选最优：分数高的优先，分数相同时优先级高的优先
        if score > best_score or (score == best_score and item["priority"] < best_priority):
            best_score = score
            best_priority = item["priority"]
            best_cls = item["class"]

    # 防误识别：没有匹配或分数为0时拒绝
    if best_cls is None or best_score <= 0:
        raise ValueError(f"无法识别模型类型: {module}.{name}")

    _logger.info("自动选择适配器: %s (模型: %s.%s, 匹配分数: %d)",
                 best_cls.__name__, module, name, best_score)
    return best_cls(model, feature_names, data_types)


# ==================== 能力辅助 ====================

def is_supported(model) -> bool:
    """
    检查模型是否支持

    参数:
        model: 模型实例

    返回:
        True 表示支持，False 表示不支持
    """
    _ensure_initialized()
    try:
        get_adapter(model)
        return True
    except Exception:
        return False


def get_supported_frameworks() -> List[str]:
    """
    获取支持的框架列表

    返回:
        支持的框架名称列表
    """
    _ensure_initialized()
    frameworks = set()
    for item in _ADAPTER_REGISTRY:
        frameworks.update(item["frameworks"])
    return sorted(frameworks) or get_frameworks_list()


def clear_registry() -> None:
    """清空注册表（主要用于测试）"""
    global _INITIALIZED
    with _REGISTRY_LOCK:
        _ADAPTER_REGISTRY.clear()
    _INITIALIZED = False
    _logger.debug("适配器注册表已清空")


# ==================== 内置适配器注册 ====================

def _register_builtin_adapters() -> None:
    """注册内置适配器"""
    from .sklearn import SklearnAdapter
    from .xgboost import XGBoostAdapter
    from .lightgbm import LightGBMAdapter
    from .catboost import CatBoostAdapter
    from .torch import TorchAdapter
    from .tensorflow import TensorFlowAdapter
    from .onnx import ONNXAdapter

    builtin_adapters = [
        (SklearnAdapter, ["sklearn"], 10, ["sklearn"], 10),
        (XGBoostAdapter, ["xgboost"], 10, ["xgboost"], 10),
        (LightGBMAdapter, ["lightgbm"], 20, ["lightgbm"], 10),
        (CatBoostAdapter, ["catboost"], 20, ["catboost"], 10),
        (TorchAdapter, ["torch", "pytorch"], 30, ["torch"], 10),
        (TensorFlowAdapter, ["tensorflow", "keras", "tf"], 30, ["tensorflow"], 10),
        (ONNXAdapter, ["onnx", "onnxruntime"], 40, ["onnx"], 10),
    ]

    for adapter_cls, keywords, priority, frameworks, weight in builtin_adapters:
        register_adapter(
            adapter_cls,
            keywords=keywords,
            priority=priority,
            frameworks=frameworks,
            weight=weight
        )