# core/logging/bootstrap.py

"""
启动日志模块

使用标准库 MemoryHandler 缓存启动日志
"""

import logging
import time
import os
from logging.handlers import MemoryHandler
from typing import Optional, List, Dict, Any

# 缓存容量配置
BOOTSTRAP_CAPACITY = 10000

# 基础应用名称
APP_NAME = os.getenv("DATAMIND_APP_NAME", "datamind").lower()

# 设置日志层级
BOOTSTRAP_LOGGER_NAME = f"{APP_NAME}.bootstrap"

# 全局 handler 实例
_bootstrap_handler: Optional[MemoryHandler] = None
_bootstrap_logger: Optional[logging.Logger] = None

# 调试模式标志
_DEBUG_MODE = os.getenv("DATAMIND_BOOTSTRAP_DEBUG", "false").lower() == "true"


def set_debug_mode(enabled: bool = True):
    """设置调试模式"""
    global _DEBUG_MODE
    _DEBUG_MODE = enabled


def _debug_log(msg: str, *args):
    """内部调试日志函数，只在调试模式开启时输出"""
    if _DEBUG_MODE:
        if args:
            print(f"[Bootstrap] {msg % args}")
        else:
            print(f"[Bootstrap] {msg}")


def debug_print_cache():
    """调试打印缓存内容（简洁版）"""
    if not _DEBUG_MODE or not _bootstrap_handler:
        return

    buffer_size = len(_bootstrap_handler.buffer) if hasattr(_bootstrap_handler, 'buffer') else 0
    print(f"\n[Bootstrap] 缓存状态: {buffer_size} 条日志")

    if buffer_size > 0 and _DEBUG_MODE:
        # 显示最新的3条作为示例
        show_count = min(3, buffer_size)
        print(f"最新 {show_count} 条日志:")
        for i, record in enumerate(_bootstrap_handler.buffer[-show_count:]):
            msg = record.getMessage()
            # 消息过长时截断
            if len(msg) > 60:
                msg = msg[:57] + "..."
            print(f"  └─ {record.levelname}: {msg}")


def debug_peek_cache(last_n: int = 10) -> List[Dict[str, Any]]:
    """
    查看最近的N条缓存日志（仅供内部使用）
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
            'time': time.strftime('%H:%M:%S', time.localtime(record.created)),
            'module': record.module,
        })

    return result


def install_bootstrap_logger():
    """
    安装启动日志缓存，必须在应用最早执行
    使用 datamind.bootstrap 作为 logger 名称
    """
    global _bootstrap_handler, _bootstrap_logger

    # 创建内存处理器
    _bootstrap_handler = MemoryHandler(
        capacity=BOOTSTRAP_CAPACITY,
        flushLevel=logging.CRITICAL,
        target=None
    )
    _bootstrap_handler.setLevel(logging.INFO)

    # 创建或获取 bootstrap logger
    _bootstrap_logger = logging.getLogger(BOOTSTRAP_LOGGER_NAME)
    _bootstrap_logger.setLevel(logging.INFO)
    _bootstrap_logger.propagate = False
    _bootstrap_logger.addHandler(_bootstrap_handler)

    _debug_log("启动日志缓存已初始化: %s (容量: %d)", BOOTSTRAP_LOGGER_NAME, BOOTSTRAP_CAPACITY)


def flush_bootstrap_logs() -> int:
    """
    将启动日志 flush 到真正的 handler
    """
    global _bootstrap_handler, _bootstrap_logger

    if not _bootstrap_handler or not _bootstrap_logger:
        _debug_log("错误: handler或logger未初始化")
        return 0

    flushed_count = 0

    # 从环境变量获取应用名称，避免导入 LoggingConfig
    app_name = os.getenv("DATAMIND_LOG_NAME", "datamind").lower()
    app_logger = logging.getLogger(app_name)

    # 找到真正的文件处理器
    target_handler = None
    for handler in app_logger.handlers:
        if not isinstance(handler, MemoryHandler):
            target_handler = handler
            _debug_log("找到目标处理器: %s", type(handler).__name__)
            break

    if not target_handler:
        _debug_log("错误: 没有找到文件处理器")
        return 0

    # 检查缓冲区
    if hasattr(_bootstrap_handler, 'buffer'):
        buffer_size = len(_bootstrap_handler.buffer)
        _debug_log("缓冲区大小: %d", buffer_size)

        if buffer_size > 0:
            # 设置目标处理器
            _bootstrap_handler.setTarget(target_handler)

            # 刷新所有缓存的日志
            _bootstrap_handler.flush()
            flushed_count = buffer_size
            _debug_log("已刷新 %d 条启动日志", flushed_count)

    # 移除 bootstrap handler
    _bootstrap_logger.removeHandler(_bootstrap_handler)
    _bootstrap_handler.close()

    # 恢复 propagate
    _bootstrap_logger.propagate = True

    # 记录刷新完成
    if flushed_count > 0:
        _bootstrap_logger.info(f"启动日志已刷新到文件处理器，共 {flushed_count} 条")

    _bootstrap_handler = None
    return flushed_count


def get_bootstrap_logger() -> logging.Logger:
    """获取启动日志器"""
    global _bootstrap_logger
    if not _bootstrap_logger:
        _bootstrap_logger = logging.getLogger(BOOTSTRAP_LOGGER_NAME)
    return _bootstrap_logger


def bootstrap_info(msg, *args, **kwargs):
    """记录 INFO 级别的启动日志"""
    logger = get_bootstrap_logger()
    logger.info(msg, *args, **kwargs)


def bootstrap_debug(msg, *args, **kwargs):
    """记录 DEBUG 级别的启动日志"""
    logger = get_bootstrap_logger()
    logger.debug(msg, *args, **kwargs)


def bootstrap_warning(msg, *args, **kwargs):
    """记录 WARNING 级别的启动日志"""
    logger = get_bootstrap_logger()
    logger.warning(msg, *args, **kwargs)


def bootstrap_error(msg, *args, **kwargs):
    """记录 ERROR 级别的启动日志"""
    logger = get_bootstrap_logger()
    logger.error(msg, *args, **kwargs)


def bootstrap_critical(msg, *args, **kwargs):
    """记录 CRITICAL 级别的启动日志"""
    logger = get_bootstrap_logger()
    logger.critical(msg, *args, **kwargs)