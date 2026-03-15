# core/logging/__init__.py
"""
日志模块

提供完整的日志管理功能
"""

from core.logging.manager import LogManager, log_manager
from core.logging.formatters import TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
from core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter
from core.logging.handlers import TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
from core.logging.cleanup import CleanupManager
from core.logging.context import get_request_id, set_request_id, RequestIdContext, with_request_id
from core.logging.debug import in_debug, set_debug, debug_print, warning_print, error_print
from core.logging.bootstrap import (
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
    'get_request_id',
    'set_request_id',
    'RequestIdContext',
    'with_request_id',
    'in_debug',
    'set_debug',
    'debug_print',
    'warning_print',
    'error_print',
    'install_bootstrap_logger',
    'flush_bootstrap_logs',
    'get_bootstrap_logger',
    'bootstrap_info',
    'bootstrap_debug',
    'bootstrap_warning',
    'bootstrap_error',
    'bootstrap_critical',
    'set_debug_mode',
]