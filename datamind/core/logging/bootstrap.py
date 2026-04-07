# datamind/core/logging/bootstrap.py

"""启动日志缓存

在日志系统完全初始化前，缓存启动期间的日志，避免初始化前的日志丢失。

核心功能：
  - install_bootstrap_logger: 安装启动日志缓存（绑定 root logger）
  - flush_bootstrap_logs: 刷新缓存的日志到正式处理器
  - bootstrap_info/debug/warning/error/critical: 记录启动日志

特性：
  - 缓存容量可配置（默认 10000 条）
  - 自动刷新：通过 MemoryHandler.setTarget() 实现
  - 零侵入：使用 Python logging 原生机制
  - 绑定 root logger：确保所有日志（包括第三方库）都被缓存
  - 资源清理：flush 后自动关闭 handler，释放内存

使用示例：
    from datamind.core.logging.bootstrap import (
        install_bootstrap_logger,
        bootstrap_info,
        flush_bootstrap_logs
    )
    from datamind.core.logging.manager import log_manager

    # 应用启动时立即安装 bootstrap logger
    install_bootstrap_logger()

    # 记录启动日志（这些日志会被缓存）
    bootstrap_info("应用正在启动...")
    bootstrap_info("加载配置中...")

    # 初始化正式日志系统
    log_manager.initialize(config)

    # 获取正式日志的处理器并刷新
    target_handler = log_manager.app_logger.handlers[0]
    flush_bootstrap_logs(target_handler)

    # 可选：自定义缓存容量
    install_bootstrap_logger(capacity=20000, level=logging.DEBUG)
"""

import os
import sys
import logging
from logging.handlers import MemoryHandler
from typing import Optional
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

# bootstrap 调试开关
_BOOTSTRAP_DEBUG = os.environ.get('DATAMIND_BOOTSTRAP_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """bootstrap 内部调试输出"""
    if _BOOTSTRAP_DEBUG:
        if args:
            print(f"[Bootstrap] {msg % args}", file=sys.stderr)
        else:
            print(f"[Bootstrap] {msg}", file=sys.stderr)


@dataclass
class BootstrapConfig:
    """启动日志配置

    - capacity: 缓存容量（最大缓存日志条数）
    - flush_level: 触发刷新的日志级别
    - level: 缓存日志级别
    """

    capacity: int = 10000
    flush_level: int = logging.CRITICAL
    level: int = logging.INFO


# 全局状态
_config: BootstrapConfig = BootstrapConfig()
_bootstrap_handler: Optional[MemoryHandler] = None
_bootstrap_logger: Optional[logging.Logger] = None
_bootstrap_initialized: bool = False
_bootstrap_flushed: bool = False


def set_bootstrap_config(config: BootstrapConfig) -> None:
    """设置启动日志配置

    参数:
        config: 启动日志配置对象

    示例:
        config = BootstrapConfig(capacity=5000, level=logging.DEBUG)
        set_bootstrap_config(config)
    """
    global _config
    _config = config
    _debug("启动日志配置已更新: capacity=%d, level=%s",
           config.capacity, logging.getLevelName(config.level))


def install_bootstrap_logger(
    capacity: Optional[int] = None,
    flush_level: Optional[int] = None,
    level: Optional[int] = None
) -> bool:
    """安装启动日志缓存，必须在应用最早执行

    参数:
        capacity: 缓存容量（默认 10000）
        flush_level: 触发刷新的日志级别（默认 CRITICAL）
        level: 缓存日志级别（默认 INFO）

    返回:
        是否成功安装

    示例:
        # 使用默认配置
        install_bootstrap_logger()

        # 自定义配置
        install_bootstrap_logger(capacity=20000, level=logging.DEBUG)
    """
    global _bootstrap_handler, _bootstrap_logger, _bootstrap_initialized, _bootstrap_flushed

    if _bootstrap_initialized:
        _debug("bootstrap logger 已初始化，跳过")
        return True

    actual_capacity = capacity if capacity is not None else _config.capacity
    actual_flush_level = flush_level if flush_level is not None else _config.flush_level
    actual_level = level if level is not None else _config.level

    try:
        _bootstrap_handler = MemoryHandler(
            capacity=actual_capacity,
            flushLevel=actual_flush_level,
            target=None
        )
        _bootstrap_handler.setLevel(actual_level)

        _bootstrap_logger = logging.getLogger()
        _bootstrap_logger.setLevel(logging.DEBUG)
        _bootstrap_logger.addHandler(_bootstrap_handler)

        _bootstrap_initialized = True
        _bootstrap_flushed = False

        _debug("启动日志缓存已安装: capacity=%d, level=%s",
               actual_capacity, logging.getLevelName(actual_level))
        return True

    except Exception as e:
        _logger.error("安装启动日志缓存失败: %s", e, exc_info=True)
        return False


def flush_bootstrap_logs(target_handler: logging.Handler, force: bool = False) -> int:
    """将启动日志刷新到正式处理器

    参数:
        target_handler: 正式日志处理器
        force: 是否强制刷新（即使已经刷新过）

    返回:
        刷新的日志条数

    示例:
        target_handler = log_manager.app_logger.handlers[0]
        flushed_count = flush_bootstrap_logs(target_handler)
        print(f"已刷新 {flushed_count} 条启动日志")
    """
    global _bootstrap_handler, _bootstrap_flushed

    if not _bootstrap_initialized:
        _logger.warning("bootstrap logger 未初始化，无法刷新")
        return 0

    if _bootstrap_flushed and not force:
        _debug("bootstrap 日志已刷新过，跳过")
        return 0

    if not _bootstrap_handler:
        _logger.warning("bootstrap handler 不存在")
        return 0

    buffer_size = len(getattr(_bootstrap_handler, 'buffer', []))
    _debug("开始刷新启动日志: %d 条", buffer_size)

    try:
        _bootstrap_handler.setTarget(target_handler)
        _bootstrap_handler.flush()

        if _bootstrap_logger:
            _bootstrap_logger.removeHandler(_bootstrap_handler)
        _bootstrap_handler.close()
        _bootstrap_handler = None
        _bootstrap_flushed = True

        _debug("已刷新 %d 条启动日志", buffer_size)
        return buffer_size

    except Exception as e:
        _logger.error("刷新启动日志失败: %s", e, exc_info=True)
        return 0


def is_initialized() -> bool:
    """检查是否已初始化

    返回:
        是否已初始化

    示例:
        if not is_initialized():
            install_bootstrap_logger()
    """
    return _bootstrap_initialized


def is_flushed() -> bool:
    """检查是否已刷新

    返回:
        是否已刷新

    示例:
        if not is_flushed():
            flush_bootstrap_logs(handler)
    """
    return _bootstrap_flushed


def get_bootstrap_logger() -> Optional[logging.Logger]:
    """获取启动日志器

    返回:
        启动日志器实例，未初始化时返回 None
    """
    return _bootstrap_logger


def bootstrap_info(msg: str, *args, **kwargs) -> None:
    """记录 INFO 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数

    示例:
        bootstrap_info("应用启动中...")
        bootstrap_info("加载模型: %s", model_name)
    """
    if _bootstrap_logger:
        _bootstrap_logger.info(msg, *args, **kwargs)
    else:
        # 降级：bootstrap 未初始化时输出到 stderr
        if args:
            print(f"[BOOTSTRAP INFO] {msg % args}")
        else:
            print(f"[BOOTSTRAP INFO] {msg}")


def bootstrap_debug(msg: str, *args, **kwargs) -> None:
    """记录 DEBUG 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    if _bootstrap_logger:
        _bootstrap_logger.debug(msg, *args, **kwargs)
    else:
        if args:
            print(f"[BOOTSTRAP DEBUG] {msg % args}")
        else:
            print(f"[BOOTSTRAP DEBUG] {msg}")


def bootstrap_warning(msg: str, *args, **kwargs) -> None:
    """记录 WARNING 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    if _bootstrap_logger:
        _bootstrap_logger.warning(msg, *args, **kwargs)
    else:
        if args:
            print(f"[BOOTSTRAP WARNING] {msg % args}")
        else:
            print(f"[BOOTSTRAP WARNING] {msg}")


def bootstrap_error(msg: str, *args, **kwargs) -> None:
    """记录 ERROR 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    if _bootstrap_logger:
        _bootstrap_logger.error(msg, *args, **kwargs)
    else:
        if args:
            print(f"[BOOTSTRAP ERROR] {msg % args}")
        else:
            print(f"[BOOTSTRAP ERROR] {msg}")


def bootstrap_critical(msg: str, *args, **kwargs) -> None:
    """记录 CRITICAL 级别的启动日志

    参数:
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外的日志参数
    """
    if _bootstrap_logger:
        _bootstrap_logger.critical(msg, *args, **kwargs)
    else:
        if args:
            print(f"[BOOTSTRAP CRITICAL] {msg % args}")
        else:
            print(f"[BOOTSTRAP CRITICAL] {msg}")


__all__ = [
    "BootstrapConfig",
    "set_bootstrap_config",
    "install_bootstrap_logger",
    "flush_bootstrap_logs",
    "is_initialized",
    "is_flushed",
    "get_bootstrap_logger",
    "bootstrap_info",
    "bootstrap_debug",
    "bootstrap_warning",
    "bootstrap_error",
    "bootstrap_critical",
]