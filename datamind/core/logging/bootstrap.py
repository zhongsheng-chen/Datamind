# Datamind/datamind/core/logging/bootstrap.py

"""启动日志缓存

在日志系统完全初始化前，缓存启动期间的日志。

使用 MemoryHandler 缓存启动日志，在日志系统初始化完成后，
将缓存的日志刷新到真正的文件处理器。

特性：
  - 缓存容量可配置（默认 10000 条）
  - 支持调试模式输出
  - 广播模式：将日志发送给所有处理器
  - 优雅刷新：确保所有启动日志都被记录

工作流程：
  - 应用启动时立即调用 install_bootstrap_logger()
  - 使用 bootstrap_info/debug/warning/error 记录启动日志
  - 日志系统初始化完成后调用 flush_bootstrap_logs()
  - 缓存的日志被刷新到真正的文件处理器
"""

import os
import time
import threading
import logging
from logging.handlers import MemoryHandler
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class BootstrapConfig:
    """启动日志配置"""
    capacity: int = 10000
    flush_level: int = logging.CRITICAL
    level: int = logging.INFO
    debug_mode: bool = False
    app_name_env: str = "DATAMIND_APP_NAME"
    log_name_env: str = "DATAMIND_LOG_NAME"
    default_app_name: str = "datamind"

    @classmethod
    def from_env(cls) -> 'BootstrapConfig':
        """从环境变量创建配置"""
        return cls(
            debug_mode=os.getenv("DATAMIND_BOOTSTRAP_DEBUG", "false").lower() == "true"
        )


_config: BootstrapConfig = BootstrapConfig.from_env()

_bootstrap_handler: Optional[MemoryHandler] = None
_bootstrap_logger: Optional[logging.Logger] = None
_bootstrap_flushed: bool = False
_bootstrap_lock: threading.Lock = threading.Lock()
_bootstrap_initialized: bool = False


def set_bootstrap_config(config: BootstrapConfig) -> None:
    """设置启动日志配置

    参数:
        config: 启动日志配置对象
    """
    global _config
    with _bootstrap_lock:
        _config = config
        _debug_log("配置已更新: capacity=%d, debug_mode=%s",
                   config.capacity, config.debug_mode)


def set_debug_mode(enabled: bool = True) -> None:
    """设置调试模式

    参数:
        enabled: 是否启用调试模式
    """
    global _config
    with _bootstrap_lock:
        _config.debug_mode = enabled
        _debug_log("调试模式: %s", "开启" if enabled else "关闭")


def _get_bootstrap_logger_name() -> str:
    """动态获取 bootstrap logger 名称

    返回:
        logger 名称
    """
    app_name = os.getenv(_config.app_name_env, _config.default_app_name).lower()
    return f"{app_name}.bootstrap"


def _debug_log(msg: str, *args: Any) -> None:
    """内部调试日志函数，只在调试模式开启时输出

    参数:
        msg: 日志消息
        *args: 消息格式化参数
    """
    if _config.debug_mode:
        if args:
            print(f"[Bootstrap] {msg % args}")
        else:
            print(f"[Bootstrap] {msg}")


def is_initialized() -> bool:
    """检查是否已初始化

    返回:
        是否已初始化
    """
    return _bootstrap_initialized


def is_flushed() -> bool:
    """检查是否已刷新

    返回:
        是否已刷新
    """
    return _bootstrap_flushed


def get_buffer_size() -> int:
    """获取当前缓存大小

    返回:
        缓存中的日志条数
    """
    if not _bootstrap_handler or not hasattr(_bootstrap_handler, 'buffer'):
        return 0
    return len(_bootstrap_handler.buffer)


def get_buffer_capacity() -> int:
    """获取缓存容量

    返回:
        缓存最大容量
    """
    return _config.capacity


def is_buffer_full() -> bool:
    """检查缓存是否已满

    返回:
        缓存是否已满
    """
    return get_buffer_size() >= _config.capacity


def debug_print_cache() -> None:
    """调试打印缓存内容（简洁版）"""
    if not _config.debug_mode:
        return

    buffer_size = get_buffer_size()
    if buffer_size == 0:
        print("[Bootstrap] 缓存为空")
        return

    print(f"\n[Bootstrap] 缓存状态: {buffer_size}/{_config.capacity} 条日志")

    if buffer_size > 0:
        show_count = min(3, buffer_size)
        print(f"最新 {show_count} 条日志:")
        for i, record in enumerate(_bootstrap_handler.buffer[-show_count:]):
            msg = record.getMessage()
            if len(msg) > 60:
                msg = msg[:57] + "..."
            print(f"  └─ {record.levelname}: {msg}")


def debug_peek_cache(last_n: int = 10) -> List[Dict[str, Any]]:
    """查看最近的N条缓存日志

    参数:
        last_n: 要查看的最近日志条数

    返回:
        日志记录列表，每条记录包含级别、消息、时间、模块等信息
    """
    if not _bootstrap_handler or not hasattr(_bootstrap_handler, 'buffer'):
        return []

    buffer = _bootstrap_handler.buffer
    if not buffer:
        return []

    result = []
    start_idx = max(0, len(buffer) - last_n)

    for record in buffer[start_idx:]:
        result.append({
            'level': logging.getLevelName(record.levelno),
            'message': record.getMessage(),
            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created)),
            'module': record.module,
            'filename': record.filename,
            'lineno': record.lineno,
        })

    return result


def debug_dump_cache() -> List[Dict[str, Any]]:
    """导出所有缓存日志

    返回:
        所有缓存的日志记录列表
    """
    return debug_peek_cache(get_buffer_size())


def install_bootstrap_logger(capacity: Optional[int] = None) -> bool:
    """安装启动日志缓存，必须在应用最早执行

    参数:
        capacity: 缓存容量，如果不指定则使用配置的默认值

    返回:
        是否成功安装
    """
    global _bootstrap_handler, _bootstrap_logger, _bootstrap_flushed, _bootstrap_initialized

    with _bootstrap_lock:
        if _bootstrap_initialized:
            _debug_log("bootstrap logger 已经初始化，跳过")
            return True

        actual_capacity = capacity if capacity is not None else _config.capacity

        try:
            _bootstrap_handler = MemoryHandler(
                capacity=actual_capacity,
                flushLevel=_config.flush_level,
                target=None
            )
            _bootstrap_handler.setLevel(_config.level)

            logger_name = _get_bootstrap_logger_name()

            _bootstrap_logger = logging.getLogger(logger_name)
            _bootstrap_logger.setLevel(_config.level)
            _bootstrap_logger.propagate = False
            _bootstrap_logger.addHandler(_bootstrap_handler)

            _bootstrap_flushed = False
            _bootstrap_initialized = True

            _debug_log("启动日志缓存已初始化: %s (容量: %d)", logger_name, actual_capacity)
            return True

        except Exception as e:
            _debug_log("初始化失败: %s", e)
            return False


def flush_bootstrap_logs(force: bool = False) -> int:
    """将启动日志 flush 到真正的 handler

    参数:
        force: 是否强制刷新（即使已经刷新过）

    返回:
        刷新的日志条数
    """
    global _bootstrap_handler, _bootstrap_logger, _bootstrap_flushed

    with _bootstrap_lock:
        if _bootstrap_flushed and not force:
            _debug_log("bootstrap 已经 flush 过，跳过")
            return 0

        if not _bootstrap_initialized:
            _debug_log("错误: bootstrap 未初始化")
            return 0

        if not _bootstrap_handler or not _bootstrap_logger:
            _debug_log("错误: handler或logger未初始化")
            return 0

        buffer = getattr(_bootstrap_handler, "buffer", [])
        buffer_size = len(buffer)

        if buffer_size == 0:
            _debug_log("缓冲区为空，无需 flush")
            return 0

        _debug_log("开始 flush bootstrap 日志: %d 条", buffer_size)

        # 优先使用环境变量指定的应用名称
        app_name = os.getenv(_config.log_name_env, _config.default_app_name).lower()
        _debug_log("尝试获取应用日志器: %s", app_name)

        app_logger = logging.getLogger(app_name)

        # 如果应用日志器没有处理器，尝试查找其他可能的日志器
        if not app_logger.handlers:
            _debug_log("应用日志器 %s 没有处理器，尝试查找其他日志器", app_name)

            # 尝试查找任何有处理器的日志器
            potential_loggers = [
                logging.getLogger(name) for name in logging.root.manager.loggerDict.keys()
                if name and not name.startswith('datamind.bootstrap')
            ]

            for logger in potential_loggers:
                if logger.handlers:
                    _debug_log("找到有处理器的日志器: %s，处理器数量: %d",
                               logger.name, len(logger.handlers))
                    app_logger = logger
                    break

        # 如果还是没有处理器，使用 root logger
        if not app_logger.handlers:
            _debug_log("警告: app_logger 没有 handler，将使用父级处理器")
            app_logger = logging.getLogger()
            if not app_logger.handlers:
                _debug_log("错误: 没有可用的处理器，跳过 flush")
                return 0

        flushed_count = _broadcast_logs(buffer, app_logger)
        _debug_log("已广播 %d 条启动日志到所有处理器", flushed_count)

        _cleanup_bootstrap()

        _bootstrap_flushed = True

        _flush_all_handlers(app_logger)

        try:
            app_logger.info(f"启动日志已刷新，共 {flushed_count} 条")
        except Exception as e:
            _debug_log("记录刷新完成日志失败: %s", e)

        return flushed_count


def _broadcast_logs(buffer: List[logging.LogRecord], app_logger: logging.Logger) -> int:
    """广播日志到所有处理器

    参数:
        buffer: 日志记录缓冲区
        app_logger: 目标日志器

    返回:
        广播的日志条数
    """
    flushed_count = 0
    for i, handler in enumerate(app_logger.handlers):
        handler_type = type(handler).__name__
        _debug_log(f"  处理器 {i}: {handler_type}")

        if handler is _bootstrap_handler:
            _debug_log("    跳过 bootstrap 自身处理器")
            continue

        try:
            for record in buffer:
                # 检查 handler 的级别是否允许该日志
                if record.levelno >= handler.level:
                    handler.handle(record)
                    flushed_count += 1
                else:
                    _debug_log(f"    跳过日志 (级别 {record.levelname} < handler级别 {logging.getLevelName(handler.level)})")

            if hasattr(handler, "flush"):
                handler.flush()
                _debug_log(f"    已刷新处理器 {i}")

        except Exception as e:
            _debug_log(f"    写入处理器 {i} 失败: {e}")

    return flushed_count


def _cleanup_bootstrap() -> None:
    """清理 bootstrap 资源"""
    global _bootstrap_handler, _bootstrap_logger

    try:
        if _bootstrap_logger and _bootstrap_handler:
            _bootstrap_logger.removeHandler(_bootstrap_handler)
            _debug_log("已从 bootstrap logger 移除 handler")
    except Exception as e:
        _debug_log(f"移除 handler 失败: {e}")

    try:
        if _bootstrap_handler:
            _bootstrap_handler.close()
            _debug_log("已关闭 bootstrap handler")
    except Exception as e:
        _debug_log(f"关闭 handler 失败: {e}")

    try:
        if _bootstrap_handler and hasattr(_bootstrap_handler, 'buffer'):
            _bootstrap_handler.buffer.clear()
            _debug_log("已清空缓冲区")
    except Exception as e:
        _debug_log(f"清空缓冲区失败: {e}")

    if _bootstrap_logger:
        _bootstrap_logger.propagate = True

    _bootstrap_handler = None


def _flush_all_handlers(logger: logging.Logger) -> None:
    """刷新所有处理器

    参数:
        logger: 日志器对象
    """
    for i, handler in enumerate(logger.handlers):
        if hasattr(handler, "flush"):
            try:
                handler.flush()
                _debug_log(f"最终刷新处理器 {i}")
            except Exception as e:
                _debug_log(f"最终刷新处理器 {i} 失败: {e}")


def get_bootstrap_logger() -> logging.Logger:
    """获取启动日志器

    返回:
        启动日志器实例
    """
    global _bootstrap_logger
    if not _bootstrap_logger:
        logger_name = _get_bootstrap_logger_name()
        _bootstrap_logger = logging.getLogger(logger_name)
    return _bootstrap_logger


def bootstrap_info(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 INFO 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    logger = get_bootstrap_logger()
    logger.info(msg, *args, **kwargs)


def bootstrap_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 DEBUG 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    logger = get_bootstrap_logger()
    logger.debug(msg, *args, **kwargs)


def bootstrap_warning(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 WARNING 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    logger = get_bootstrap_logger()
    logger.warning(msg, *args, **kwargs)


def bootstrap_error(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 ERROR 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    logger = get_bootstrap_logger()
    logger.error(msg, *args, **kwargs)


def bootstrap_critical(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 CRITICAL 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    logger = get_bootstrap_logger()
    logger.critical(msg, *args, **kwargs)