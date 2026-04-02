# datamind/core/logging/__init__.py

"""日志模块

提供完整的日志管理功能，包括：
  - 日志管理器（LogManager）
  - 日志格式化器（JSON/Text）
  - 日志过滤器（请求ID、敏感数据、采样）
  - 日志处理器（文件轮转、异步处理）
  - 日志清理管理
  - 请求上下文（request_id/trace_id/span_id）
  - 调试工具（debug_print）
  - 启动日志缓存（bootstrap）
"""

import importlib
import logging
import sys
from typing import TYPE_CHECKING

from datamind.core.logging.manager import log_manager

if TYPE_CHECKING:
    from datamind.core.logging.manager import LogManager
    from datamind.core.logging.formatters import TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
    from datamind.core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter
    from datamind.core.logging.handlers import TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
    from datamind.core.logging.cleanup import CleanupManager


# ==================== 全局 fallback logger ====================

_fallback_logger = logging.getLogger("datamind.fallback")
_fallback_logger.propagate = False

if not _fallback_logger.handlers:
    _console_handler = logging.StreamHandler(sys.stderr)
    _console_handler.setLevel(logging.WARNING)
    _fallback_logger.addHandler(_console_handler)


# ==================== 安全获取 logger 的工具函数 ====================

def get_logger(name: str = None) -> logging.Logger:
    """
    安全获取日志记录器，避免循环导入和未初始化问题

    策略：
        1. 优先使用日志管理器的单例应用日志记录器
        2. 如果不可用，使用标准日志记录器
        3. 确保永远不会返回空值
        4. 支持子日志记录器（通过获取子记录器）

    参数:
        name: 日志记录器名称（可选）

    返回:
        日志记录器实例
    """
    try:
        # 直接使用已导入的单例 log_manager
        logger = log_manager.app_logger
        if logger is not None:
            if name is None:
                return logger
            # 返回子日志记录器，保持层级关系
            return logger.getChild(name)
    except Exception as e:
        _fallback_logger.debug("日志管理器初始化失败，降级使用标准日志记录器: %s", e)

    # 兜底：使用标准日志记录器
    return logging.getLogger(name or __name__)


# ==================== 懒加载缓存 ====================

_LAZY_CACHE = {}


def _lazy_import(module_name: str, attr_name: str = None):
    """安全的懒导入，带缓存，使用 importlib 标准库"""
    cache_key = f"{module_name}:{attr_name}" if attr_name else module_name
    if cache_key in _LAZY_CACHE:
        return _LAZY_CACHE[cache_key]

    try:
        module = importlib.import_module(module_name)
        if attr_name:
            result = getattr(module, attr_name)
        else:
            result = module
        _LAZY_CACHE[cache_key] = result
        return result
    except ImportError as e:
        _fallback_logger.debug("懒导入失败: %s, 错误: %s", cache_key, e)
        raise


def __getattr__(name: str):
    # 使用懒导入缓存，避免重复导入
    if name == "LogManager":
        from datamind.core.logging.manager import LogManager
        return LogManager

    elif name in {"TimezoneFormatter", "CustomJsonFormatter", "CustomTextFormatter"}:
        return _lazy_import("datamind.core.logging.formatters", name)

    elif name in {"RequestIdFilter", "SensitiveDataFilter", "SamplingFilter"}:
        return _lazy_import("datamind.core.logging.filters", name)

    elif name in {"TimeRotatingFileHandlerWithTimezone", "AsyncLogHandler"}:
        return _lazy_import("datamind.core.logging.handlers", name)

    elif name == "CleanupManager":
        return _lazy_import("datamind.core.logging.cleanup", "CleanupManager")

    elif name == "context":
        return _lazy_import("datamind.core.logging.context")

    elif name in {
        "get_request_id", "set_request_id", "clear_request_id", "has_request_id",
        "get_trace_id", "set_trace_id", "clear_trace_id", "has_trace_id",
        "get_span_id", "set_span_id", "clear_span_id", "has_span_id",
        "get_parent_span_id", "set_parent_span_id", "clear_parent_span_id", "has_parent_span_id",
        "ensure_request", "ensure_trace", "ensure_span",
        "with_request_id", "with_span",
        "RequestIdContext", "SpanContext", "RequestContext"
    }:
        context_mod = _lazy_import("datamind.core.logging.context")
        return getattr(context_mod, name)

    elif name in {
        "in_debug", "set_debug", "debug_print", "warning_print", "error_print"
    }:
        return _lazy_import("datamind.core.logging.debug", name)

    elif name in {
        "install_bootstrap_logger",
        "flush_bootstrap_logs",
        "get_bootstrap_logger",
        "bootstrap_info",
        "bootstrap_debug",
        "bootstrap_warning",
        "bootstrap_error",
        "bootstrap_critical",
        "set_debug_mode",
    }:
        return _lazy_import("datamind.core.logging.bootstrap", name)

    raise AttributeError(f"模块 'datamind.core.logging' 没有属性 '{name}'")


def log_audit(*args, **kwargs):
    """审计日志"""
    try:
        return log_manager.log_audit(*args, **kwargs)
    except Exception as e:
        _fallback_logger.warning("[降级审计日志] %s, 参数: %s", e, kwargs or args)


def log_access(*args, **kwargs):
    """访问日志"""
    try:
        return log_manager.log_access(*args, **kwargs)
    except Exception as e:
        _fallback_logger.warning("[降级访问日志] %s, 参数: %s", e, kwargs or args)


def log_performance(*args, **kwargs):
    """性能日志"""
    try:
        return log_manager.log_performance(*args, **kwargs)
    except Exception as e:
        _fallback_logger.warning("[降级性能日志] %s, 参数: %s", e, kwargs or args)


__all__ = [
    'LogManager',
    'log_manager',
    'get_logger',
    'TimezoneFormatter',
    'CustomJsonFormatter',
    'CustomTextFormatter',
    'RequestIdFilter',
    'SensitiveDataFilter',
    'SamplingFilter',
    'TimeRotatingFileHandlerWithTimezone',
    'AsyncLogHandler',
    'CleanupManager',
    'context',
    'log_audit',
    'log_access',
    'log_performance',
]