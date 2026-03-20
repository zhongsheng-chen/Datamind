# Datamind/datamind/core/logging/debug.py

"""调试打印工具

提供轻量级的调试输出功能，用于开发阶段快速定位问题。

特性：
  - 级别区分：TRACE/DEBUG/INFO/WARNING/ERROR/CRITICAL
  - 防止递归：避免调试输出导致无限循环
  - 线程安全：使用 threading.local 保护
  - 可配置：通过环境变量或配置控制是否输出
  - 格式化输出：统一的时间戳和格式

使用方式：
    debug_print("MyClass", "消息: %s", value)
    warning_print("MyClass", "警告: %s", warning)
    error_print("MyClass", "错误: %s", error)
"""

import sys
import threading
from enum import Enum
from datetime import datetime
from typing import Optional, Any, Dict


class LogLevel(Enum):
    """日志级别枚举"""
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    FATAL = 5  # CRITICAL 的别名

    @property
    def prefix(self) -> str:
        """获取级别前缀"""
        prefixes = {
            LogLevel.TRACE: "[TRACE]",
            LogLevel.DEBUG: "[DEBUG]",
            LogLevel.INFO: "[INFO]",
            LogLevel.WARNING: "[WARNING]",
            LogLevel.ERROR: "[ERROR]",
            LogLevel.CRITICAL: "[CRITICAL]",
        }
        return prefixes.get(self, "[DEBUG]")

    @property
    def color_code(self) -> str:
        """获取ANSI颜色代码（用于终端彩色输出）"""
        colors = {
            LogLevel.TRACE: "\033[90m",  # 灰色
            LogLevel.DEBUG: "\033[36m",  # 青色
            LogLevel.INFO: "\033[32m",  # 绿色
            LogLevel.WARNING: "\033[33m",  # 黄色
            LogLevel.ERROR: "\033[31m",  # 红色
            LogLevel.CRITICAL: "\033[35m",  # 紫色
        }
        return colors.get(self, "\033[0m")

    @staticmethod
    def from_string(level: str) -> 'LogLevel':
        """从字符串转换为枚举

        参数:
            level: 级别字符串（如 "INFO", "debug"）

        返回:
            对应的日志级别枚举
        """
        level_upper = level.upper()
        for log_level in LogLevel:
            if log_level.name == level_upper:
                return log_level
        return LogLevel.INFO


# 延迟导入，避免循环依赖
_LOG_CONFIG = None
_CONFIG_LOCK = threading.Lock()

# 防止递归的保护标志
_IN_DEBUG = threading.local()

# 输出控制
_ENABLE_COLORS = True
_MIN_LEVEL = LogLevel.DEBUG  # 默认最低级别
_ENABLE_DEBUG = True  # 是否启用调试输出


def _get_log_config():
    """获取日志配置（懒加载）

    返回:
        日志配置对象，如果未配置则返回 None
    """
    global _LOG_CONFIG
    if _LOG_CONFIG is None:
        with _CONFIG_LOCK:
            if _LOG_CONFIG is None:
                try:
                    from datamind.config import LoggingConfig
                    _LOG_CONFIG = LoggingConfig.load()
                    # 根据配置设置最小级别
                    if _LOG_CONFIG and hasattr(_LOG_CONFIG, 'debug_level'):
                        _set_min_level(_LOG_CONFIG.debug_level)
                except ImportError:
                    _LOG_CONFIG = False
    return _LOG_CONFIG if _LOG_CONFIG is not False else None


def _set_min_level(level: str) -> None:
    """设置最小输出级别

    参数:
        level: 级别字符串（如 "INFO", "DEBUG"）
    """
    global _MIN_LEVEL
    try:
        _MIN_LEVEL = LogLevel.from_string(level)
    except Exception:
        pass


def set_min_level(level: str) -> None:
    """设置最小输出级别（公共接口）

    参数:
        level: 级别字符串（如 "INFO", "DEBUG"）
    """
    _set_min_level(level)


def set_color_enabled(enabled: bool) -> None:
    """设置是否启用彩色输出

    参数:
        enabled: 是否启用彩色输出
    """
    global _ENABLE_COLORS
    _ENABLE_COLORS = enabled


def set_debug_enabled(enabled: bool) -> None:
    """设置是否启用调试输出

    参数:
        enabled: 是否启用调试输出
    """
    global _ENABLE_DEBUG
    _ENABLE_DEBUG = enabled


def _format_timestamp(dt: Optional[datetime] = None) -> str:
    """格式化时间戳

    参数:
        dt: 时间对象，如果不提供则使用当前时间

    返回:
        格式化后的时间戳字符串（格式：YYYY-MM-DD HH:MM:SS,mmm）
    """
    if dt is None:
        dt = datetime.now()

    ms = dt.microsecond // 1000
    return f"{dt:%Y-%m-%d %H:%M:%S},{ms:03d}"


def in_debug() -> bool:
    """检查是否正在调试输出中

    返回:
        是否正在调试输出中
    """
    return getattr(_IN_DEBUG, 'value', False)


def set_debug(value: bool) -> None:
    """设置调试输出状态

    参数:
        value: 调试输出状态
    """
    _IN_DEBUG.value = value


def _should_output(level: LogLevel) -> bool:
    """判断是否应该输出该级别的日志

    参数:
        level: 日志级别

    返回:
        是否应该输出
    """
    if not _ENABLE_DEBUG:
        return False
    return level.value >= _MIN_LEVEL.value


def _base_print(component: str, msg: str, *args: Any, level: LogLevel) -> None:
    """基础打印函数

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
        level: 日志级别枚举
    """
    # 检查是否应该输出
    if not _should_output(level):
        return

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

        # 构建输出行
        if _ENABLE_COLORS:
            # 彩色输出
            color_reset = "\033[0m"
            prefix = f"{level.color_code}{level.prefix}{color_reset}"
            output = f"{timestamp} {prefix} {component}: {formatted_msg}"
        else:
            # 普通输出
            output = f"{timestamp} {level.prefix} {component}: {formatted_msg}"

        # 输出到 stderr
        print(output, file=sys.stderr)

    except Exception:
        # 调试输出绝不能影响主程序，出错时静默失败
        pass
    finally:
        set_debug(False)


def trace_print(component: str, msg: str, *args: Any) -> None:
    """追踪打印函数 - TRACE级别（最详细的调试信息）

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.TRACE)


def debug_print(component: str, msg: str, *args: Any) -> None:
    """调试打印函数 - DEBUG级别

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.DEBUG)


def info_print(component: str, msg: str, *args: Any) -> None:
    """信息打印函数 - INFO级别

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.INFO)


def warning_print(component: str, msg: str, *args: Any) -> None:
    """警告打印函数 - WARNING级别

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.WARNING)


def error_print(component: str, msg: str, *args: Any) -> None:
    """错误打印函数 - ERROR级别

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.ERROR)


def critical_print(component: str, msg: str, *args: Any) -> None:
    """严重错误打印函数 - CRITICAL级别

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.CRITICAL)


def fatal_print(component: str, msg: str, *args: Any) -> None:
    """致命错误打印函数 - FATAL级别（CRITICAL的别名）

    参数:
        component: 组件名称（通常是类名）
        msg: 消息模板
        *args: 消息参数
    """
    _base_print(component, msg, *args, level=LogLevel.FATAL)


def log_print(component: str, level: str, msg: str, *args: Any) -> None:
    """通用日志打印函数

    参数:
        component: 组件名称（通常是类名）
        level: 日志级别字符串（如 "INFO", "DEBUG"）
        msg: 消息模板
        *args: 消息参数

    示例:
        log_print("DatabaseManager", "INFO", "数据库连接成功")
        log_print("DatabaseManager", "ERROR", "连接失败: %s", error_msg)
    """
    try:
        log_level = LogLevel.from_string(level)
        _base_print(component, msg, *args, level=log_level)
    except Exception:
        # 无效级别时默认使用 INFO
        _base_print(component, msg, *args, level=LogLevel.INFO)


def get_debug_stats() -> Dict[str, Any]:
    """获取调试工具统计信息

    返回:
        包含配置和状态的字典
    """
    return {
        'enabled': _ENABLE_DEBUG,
        'min_level': _MIN_LEVEL.name,
        'colors_enabled': _ENABLE_COLORS,
        'in_debug': in_debug(),
        'config_loaded': _LOG_CONFIG is not None and _LOG_CONFIG is not False,
    }