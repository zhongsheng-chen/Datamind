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

from typing import List, Optional, Type, Dict, Any, Callable

from datamind.core.logging.manager import LogManager
from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.common.frameworks import get_supported_frameworks as get_frameworks_list

_log_manager = LogManager()
_logger = _log_manager.app_logger

# ==================== 注册表 ====================

_ADAPTER_REGISTRY: List[Dict[str, Any]] = []


# ==================== 注册接口 ====================

def register_adapter(
    adapter_cls: Type[BaseModelAdapter],
    keywords: List[str],
    priority: int = 100,
    frameworks: Optional[List[str]] = None,
    can_handle: Optional[Callable] = None
) -> None:
    """
    注册适配器

    参数:
        adapter_cls: 适配器类
        keywords: 用于识别模型的关键字列表（可重复以增加权重）
        priority: 优先级（数字越小优先级越高，默认100）
        frameworks: 显式支持的框架列表
        can_handle: 可选的自定义判断函数，签名: (model) -> bool
    """
    if not keywords and not frameworks and can_handle is None:
        raise ValueError("注册适配器必须提供 keywords、frameworks 或 can_handle 其中之一")

    # 防重复注册
    for item in _ADAPTER_REGISTRY:
        if item["class"] == adapter_cls:
            _logger.debug("适配器已注册，跳过: %s", adapter_cls.__name__)
            return

    record = {
        "class": adapter_cls,
        "keywords": [k.lower() for k in keywords],
        "priority": priority,
        "frameworks": [f.lower() for f in (frameworks or [])],
        "can_handle": can_handle
    }

    _ADAPTER_REGISTRY.append(record)
    _ADAPTER_REGISTRY.sort(key=lambda x: x["priority"])

    _logger.debug(
        "注册适配器: %s, 优先级: %d, 关键字数: %d, 框架数: %d, 自定义判断: %s",
        adapter_cls.__name__,
        priority,
        len(keywords),
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
    for i, item in enumerate(_ADAPTER_REGISTRY):
        if item["class"] == adapter_cls:
            _ADAPTER_REGISTRY.pop(i)
            _logger.debug("注销适配器: %s", adapter_cls.__name__)
            return True
    return False


# ==================== 核心：获取适配器 ====================

def get_adapter(
    model,
    framework: Optional[str] = None,
    feature_names: Optional[List[str]] = None,
    transformer: Optional[Any] = None
) -> BaseModelAdapter:
    """
    获取模型适配器

    优先级：
        1. 显式 framework（生产推荐）
        2. 统一评分（can_handle + keywords）
        3. can_handle 权重 1000，keywords 权重 1

    参数:
        model: 训练好的模型
        framework: 框架名称（可选，推荐显式指定）
        feature_names: 特征名称列表（可选）
        transformer: WOE转换器（可选，评分卡模型使用）

    返回:
        BaseModelAdapter 实例

    异常:
        ValueError: 不支持的模型类型
    """
    # ---------- 显式模式（生产推荐） ----------
    if framework:
        fw = framework.lower()

        for item in _ADAPTER_REGISTRY:
            if fw in item["frameworks"]:
                _logger.info("使用显式框架: %s -> %s", fw, item["class"].__name__)
                return item["class"](model, feature_names, transformer=transformer)

        raise ValueError(f"不支持的框架: {framework}")

    # ---------- 自动识别（统一评分） ----------
    module = model.__class__.__module__.lower()
    name = model.__class__.__name__.lower()

    _logger.debug("自动识别模型: %s.%s", module, name)

    best_score = 0
    best_adapter = None

    for item in _ADAPTER_REGISTRY:
        score = 0

        # ---------- can_handle（强匹配，权重 1000） ----------
        if item["can_handle"] is not None:
            try:
                if item["can_handle"](model):
                    score += 1000
                    _logger.debug("can_handle 匹配: %s, 加分 1000", item["class"].__name__)
            except Exception as e:
                _logger.debug("can_handle 执行失败: %s, %s", item["class"].__name__, e)

        # ---------- keyword（弱匹配，权重 1） ----------
        kw_score = sum(
            1 for kw in item["keywords"]
            if kw in module or kw in name
        )
        score += kw_score

        if kw_score > 0:
            _logger.debug("keyword 匹配: %s, 加分 %d", item["class"].__name__, kw_score)

        # ---------- 更新最佳匹配 ----------
        if score > best_score:
            best_score = score
            best_adapter = item["class"]
            _logger.debug("更新最佳匹配: %s, 总分: %d", best_adapter.__name__, best_score)

    # ---------- 防误识别 ----------
    if best_score == 0 or best_adapter is None:
        raise ValueError(f"无法识别模型类型: {module}.{name}")

    _logger.info("最终选择适配器: %s (匹配分数: %d)", best_adapter.__name__, best_score)
    return best_adapter(model, feature_names, transformer=transformer)


# ==================== 能力辅助 ====================

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
    except Exception:
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
    _logger.debug("适配器注册表已清空")


# ==================== 内置适配器 ====================

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
        register_adapter(
            adapter_cls,
            keywords=keywords,
            priority=priority,
            frameworks=frameworks
        )


# 初始化内置适配器
_register_builtin_adapters()