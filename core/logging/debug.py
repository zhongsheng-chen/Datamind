# core/logging/debug.py

import threading
import sys
from datetime import datetime
from typing import Optional
import pytz

# 延迟导入，避免循环依赖
_LOG_CONFIG = None
_CONFIG_LOCK = threading.Lock()

# 调试递归保护
_IN_DEBUG = threading.local()


def _get_log_config():
    """获取日志配置（懒加载）"""
    global _LOG_CONFIG
    if _LOG_CONFIG is None:
        with _CONFIG_LOCK:
            if _LOG_CONFIG is None:
                try:
                    from config.logging_config import LoggingConfig
                    _LOG_CONFIG = LoggingConfig.load()
                except ImportError:
                    _LOG_CONFIG = False
    return _LOG_CONFIG if _LOG_CONFIG is not False else None


def _format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    根据配置格式化时间戳
    """
    config = _get_log_config()

    if dt is None:
        dt = datetime.now()

    if config:
        # 使用时区配置
        if config.timezone.value != 'LOCAL':
            try:
                tz = pytz.timezone(config.timezone.value)
                dt = datetime.now(tz)
            except:
                pass

        # 使用配置的时间格式
        return dt.strftime(config.text_datetime_format)[:-3]  # 默认毫秒
    else:
        # 默认格式
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def in_debug():
    """检查是否在调试中"""
    return getattr(_IN_DEBUG, 'value', False)


def set_debug(value: bool):
    """设置调试状态"""
    _IN_DEBUG.value = value


def debug_print(component: str, msg, *args):
    """
    统一的调试输出函数
    """
    if in_debug():
        return

    set_debug(True)
    try:
        timestamp = _format_timestamp()

        if args:
            formatted_msg = f"[{timestamp}][{component}] {msg}" % args
        else:
            formatted_msg = f"[{timestamp}][{component}] {msg}"

        print(formatted_msg, file=sys.stderr)
    finally:
        set_debug(False)