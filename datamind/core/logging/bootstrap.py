# Datamind/datamind/core/logging/bootstrap.py

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

# 全局 handler 实例
_bootstrap_handler: Optional[MemoryHandler] = None
_bootstrap_logger: Optional[logging.Logger] = None
_bootstrap_flushed: bool = False

# 调试模式标志
_DEBUG_MODE = os.getenv("DATAMIND_BOOTSTRAP_DEBUG", "false").lower() == "true"


def _get_bootstrap_logger_name() -> str:
    """动态获取 bootstrap logger 名称"""
    app_name = os.getenv("DATAMIND_APP_NAME", "datamind").lower()
    return f"{app_name}.bootstrap"


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
        show_count = min(3, buffer_size)
        print(f"最新 {show_count} 条日志:")
        for i, record in enumerate(_bootstrap_handler.buffer[-show_count:]):
            msg = record.getMessage()
            if len(msg) > 60:
                msg = msg[:57] + "..."
            print(f"  └─ {record.levelname}: {msg}")


def debug_peek_cache(last_n: int = 10) -> List[Dict[str, Any]]:
    """查看最近的N条缓存日志（仅供内部使用）"""
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
    使用动态 logger 名称
    """
    global _bootstrap_handler, _bootstrap_logger, _bootstrap_flushed

    # 创建内存处理器
    _bootstrap_handler = MemoryHandler(
        capacity=BOOTSTRAP_CAPACITY,
        flushLevel=logging.CRITICAL,
        target=None
    )
    _bootstrap_handler.setLevel(logging.INFO)

    # 动态获取 logger 名称
    logger_name = _get_bootstrap_logger_name()

    # 创建或获取 bootstrap logger
    _bootstrap_logger = logging.getLogger(logger_name)
    _bootstrap_logger.setLevel(logging.INFO)
    _bootstrap_logger.propagate = False
    _bootstrap_logger.addHandler(_bootstrap_handler)

    _bootstrap_flushed = False
    _debug_log("启动日志缓存已初始化: %s (容量: %d)", logger_name, BOOTSTRAP_CAPACITY)


def flush_bootstrap_logs() -> int:
    """
    将启动日志 flush 到真正的 handler
    采用广播模式：将缓存的日志发送给 app_logger 的所有处理器
    """
    global _bootstrap_handler, _bootstrap_logger, _bootstrap_flushed

    # 如果已经 flush 过，直接返回
    if _bootstrap_flushed:
        _debug_log("bootstrap 已经 flush 过，跳过")
        return 0

    if not _bootstrap_handler or not _bootstrap_logger:
        _debug_log("错误: handler或logger未初始化")
        return 0

    # 创建应用日志器
    app_name = os.getenv("DATAMIND_LOG_NAME", "datamind").lower()
    app_logger = logging.getLogger(app_name)

    if not app_logger.handlers:
        _debug_log("错误: app_logger 没有 handler，跳过 flush")
        return 0

    # 获取缓冲区内容
    buffer = getattr(_bootstrap_handler, "buffer", [])
    buffer_size = len(buffer)

    if buffer_size == 0:
        _debug_log("缓冲区为空，无需 flush")
        return 0

    _debug_log("开始 flush bootstrap 日志: %d 条", buffer_size)
    _debug_log(f"应用日志器处理器数量: {len(app_logger.handlers)}")

    # 广播模式：将日志发送给所有处理器
    for i, handler in enumerate(app_logger.handlers):
        handler_type = type(handler).__name__
        _debug_log(f"  处理器 {i}: {handler_type}")

        # 跳过 bootstrap 自己（避免循环）
        if handler is _bootstrap_handler:
            _debug_log("    跳过 bootstrap 自身处理器")
            continue

        try:
            # 将缓冲区中的所有记录发送给当前处理器
            for record in buffer:
                handler.handle(record)

            # 尝试刷新处理器（确保写入）
            if hasattr(handler, "flush"):
                handler.flush()
                _debug_log(f"    已刷新处理器 {i}")

        except Exception as e:
            _debug_log(f"    写入处理器 {i} 失败: {e}")

    flushed_count = buffer_size
    _debug_log("已广播 %d 条启动日志到所有处理器", flushed_count)

    # 清理 bootstrap 资源
    try:
        _bootstrap_logger.removeHandler(_bootstrap_handler)
        _debug_log("已从 bootstrap logger 移除 handler")
    except Exception as e:
        _debug_log(f"移除 handler 失败: {e}")

    try:
        _bootstrap_handler.close()
        _debug_log("已关闭 bootstrap handler")
    except Exception as e:
        _debug_log(f"关闭 handler 失败: {e}")

    try:
        # 清空缓冲区
        buffer.clear()
        _debug_log("已清空缓冲区")
    except Exception as e:
        _debug_log(f"清空缓冲区失败: {e}")

    # 恢复 propagate，让后续日志可以正常传播
    _bootstrap_logger.propagate = True

    # 标记为已 flush
    _bootstrap_handler = None
    _bootstrap_flushed = True

    # 再次强制刷新所有处理器（确保所有日志都已写入）
    for i, handler in enumerate(app_logger.handlers):
        if hasattr(handler, "flush"):
            try:
                handler.flush()
                _debug_log(f"最终刷新处理器 {i}")
            except Exception as e:
                _debug_log(f"最终刷新处理器 {i} 失败: {e}")

    # 记录刷新完成（使用 app_logger 而不是 bootstrap）
    try:
        app_logger.info(f"启动日志已刷新，共 {flushed_count} 条")
        _debug_log(f"已记录刷新完成日志")
    except Exception as e:
        _debug_log(f"记录刷新完成日志失败: {e}")

    return flushed_count


def get_bootstrap_logger() -> logging.Logger:
    """获取启动日志器"""
    global _bootstrap_logger
    if not _bootstrap_logger:
        logger_name = _get_bootstrap_logger_name()
        _bootstrap_logger = logging.getLogger(logger_name)
    return _bootstrap_logger


# 日志记录辅助函数保持不变
def bootstrap_info(msg, *args, **kwargs):
    logger = get_bootstrap_logger()
    logger.info(msg, *args, **kwargs)


def bootstrap_debug(msg, *args, **kwargs):
    logger = get_bootstrap_logger()
    logger.debug(msg, *args, **kwargs)


def bootstrap_warning(msg, *args, **kwargs):
    logger = get_bootstrap_logger()
    logger.warning(msg, *args, **kwargs)


def bootstrap_error(msg, *args, **kwargs):
    logger = get_bootstrap_logger()
    logger.error(msg, *args, **kwargs)


def bootstrap_critical(msg, *args, **kwargs):
    logger = get_bootstrap_logger()
    logger.critical(msg, *args, **kwargs)