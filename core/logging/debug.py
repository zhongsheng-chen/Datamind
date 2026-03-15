# core/logging/debug.py

import sys
import pytz
import threading
from datetime import datetime
from typing import Optional

# 延迟导入，避免循环依赖
_LOG_CONFIG = None
_CONFIG_LOCK = threading.Lock()

# 防止递归的保护标志
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


def _format_timestamp(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now()

    ms = dt.microsecond // 1000
    return f"{dt:%Y-%m-%d %H:%M:%S},{ms:03d}"

def in_debug():
    """检查是否正在调试输出中"""
    return getattr(_IN_DEBUG, 'value', False)


def set_debug(value: bool):
    """设置调试输出状态"""
    _IN_DEBUG.value = value


def _base_print(component: str, msg, *args, level: str):
    """
    基础打印函数

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
        level: 日志级别 (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # 防止递归调用
    if in_debug():
        return

    set_debug(True)
    try:
        # 格式化时间戳
        timestamp = _format_timestamp()

        # 格式化消息
        if args:
            formatted_msg = msg % args
        else:
            formatted_msg = msg

        # 根据级别选择前缀和颜色（可选）
        prefix_map = {
            "TRACE": "[TRACE]",
            "DEBUG": "[DEBUG]",
            "INFO": "[INFO]",
            "WARNING": "[WARNING]",
            "ERROR": "[ERROR]",
            "CRITICAL": "[CRITICAL]",
            "FATAL": "[FATAL]"
        }
        prefix = prefix_map.get(level, "[DEBUG]")

        # 统一打印格式：时间 [级别] 组件名: 消息
        print(f"{timestamp} {prefix} {component}: {formatted_msg}", file=sys.stderr)

    except Exception:
        # 调试输出绝不能影响主程序，出错时静默失败
        pass
    finally:
        set_debug(False)


def trace_print(component: str, msg, *args):
    """
    追踪打印函数 - TRACE级别（最详细的调试信息）

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="TRACE")


def debug_print(component: str, msg, *args):
    """
    调试打印函数 - DEBUG级别

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="DEBUG")


def info_print(component: str, msg, *args):
    """
    信息打印函数 - INFO级别

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="INFO")


def warning_print(component: str, msg, *args):
    """
    警告打印函数 - WARNING级别

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="WARNING")


def error_print(component: str, msg, *args):
    """
    错误打印函数 - ERROR级别

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="ERROR")


def critical_print(component: str, msg, *args):
    """
    严重错误打印函数 - CRITICAL级别

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="CRITICAL")


def fatal_print(component: str, msg, *args):
    """
    致命错误打印函数 - FATAL级别（CRITICAL的别名）

    Args:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level="FATAL")


# 为了方便，也可以提供一个统一的打印函数，通过参数控制级别
def log_print(component: str, level: str, msg, *args):
    """
    通用日志打印函数

    Args:
        component: 组件名称（通常是类名）
        level: 日志级别
        msg: 消息模板
        *args: 消息参数

    Example:
        log_print("DatabaseManager", "INFO", "数据库连接成功")
        log_print("DatabaseManager", "ERROR", "连接失败: %s", error_msg)
    """
    _base_print(component, msg, *args, level=level.upper())