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

from typing import TYPE_CHECKING

from datamind.core.logging.manager import log_manager

if TYPE_CHECKING:
    from datamind.core.logging.manager import LogManager
    from datamind.core.logging.formatters import TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
    from datamind.core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter
    from datamind.core.logging.handlers import TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
    from datamind.core.logging.cleanup import CleanupManager


def __getattr__(name: str):
    if name == "LogManager":
        from datamind.core.logging.manager import LogManager
        return LogManager

    elif name in {"TimezoneFormatter", "CustomJsonFormatter", "CustomTextFormatter"}:
        from datamind.core.logging.formatters import (
            TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
        )
        return {
            "TimezoneFormatter": TimezoneFormatter,
            "CustomJsonFormatter": CustomJsonFormatter,
            "CustomTextFormatter": CustomTextFormatter,
        }[name]

    elif name in {"RequestIdFilter", "SensitiveDataFilter", "SamplingFilter"}:
        from datamind.core.logging.filters import (
            RequestIdFilter, SensitiveDataFilter, SamplingFilter
        )
        return {
            "RequestIdFilter": RequestIdFilter,
            "SensitiveDataFilter": SensitiveDataFilter,
            "SamplingFilter": SamplingFilter,
        }[name]

    elif name in {"TimeRotatingFileHandlerWithTimezone", "AsyncLogHandler"}:
        from datamind.core.logging.handlers import (
            TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
        )
        return {
            "TimeRotatingFileHandlerWithTimezone": TimeRotatingFileHandlerWithTimezone,
            "AsyncLogHandler": AsyncLogHandler,
        }[name]

    elif name == "CleanupManager":
        from datamind.core.logging.cleanup import CleanupManager
        return CleanupManager

    elif name == "context":
        from datamind.core.logging import context
        return context

    elif name in {
        "get_request_id", "set_request_id", "clear_request_id", "has_request_id",
        "get_trace_id", "set_trace_id", "clear_trace_id", "has_trace_id",
        "get_span_id", "set_span_id", "clear_span_id", "has_span_id",
        "get_parent_span_id", "set_parent_span_id", "clear_parent_span_id", "has_parent_span_id",
        "ensure_request", "ensure_trace", "ensure_span",
        "with_request_id", "with_span",
        "RequestIdContext", "SpanContext", "RequestContext"
    }:
        from datamind.core.logging import context
        return getattr(context, name)

    elif name in {
        "in_debug", "set_debug", "debug_print", "warning_print", "error_print"
    }:
        from datamind.core.logging.debug import (
            in_debug, set_debug, debug_print, warning_print, error_print
        )
        return {
            "in_debug": in_debug,
            "set_debug": set_debug,
            "debug_print": debug_print,
            "warning_print": warning_print,
            "error_print": error_print,
        }[name]

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
        from datamind.core.logging.bootstrap import (
            install_bootstrap_logger,
            flush_bootstrap_logs,
            get_bootstrap_logger,
            bootstrap_info,
            bootstrap_debug,
            bootstrap_warning,
            bootstrap_error,
            bootstrap_critical,
            set_debug_mode,
        )
        return {
            "install_bootstrap_logger": install_bootstrap_logger,
            "flush_bootstrap_logs": flush_bootstrap_logs,
            "get_bootstrap_logger": get_bootstrap_logger,
            "bootstrap_info": bootstrap_info,
            "bootstrap_debug": bootstrap_debug,
            "bootstrap_warning": bootstrap_warning,
            "bootstrap_error": bootstrap_error,
            "bootstrap_critical": bootstrap_critical,
            "set_debug_mode": set_debug_mode,
        }[name]

    raise AttributeError(f"module 'datamind.core.logging' has no attribute '{name}'")


def log_audit(*args, **kwargs):
    """审计日志"""
    try:
        from datamind.core.logging import log_manager
        return log_manager.log_audit(*args, **kwargs)
    except Exception:
        import logging
        logging.getLogger().warning("[FALLBACK AUDIT] %s", kwargs or args)


def log_access(*args, **kwargs):
    """访问日志"""
    try:
        from datamind.core.logging import log_manager
        return log_manager.log_access(*args, **kwargs)
    except Exception:
        import logging
        logging.getLogger().warning("[FALLBACK ACCESS] %s", kwargs or args)


def log_performance(*args, **kwargs):
    """性能日志"""
    try:
        from datamind.core.logging import log_manager
        return log_manager.log_performance(*args, **kwargs)
    except Exception:
        import logging
        logging.getLogger().warning("[FALLBACK PERFORMANCE] %s", kwargs or args)


__all__ = [
    'LogManager',
    'log_manager',
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