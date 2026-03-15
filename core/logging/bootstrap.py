# core/logging/bootstrap.py

"""
启动日志模块

使用标准库 MemoryHandler 缓存启动日志
"""

import logging
import time
from logging.handlers import MemoryHandler
from typing import Optional, List, Dict, Any

# 缓存容量配置
BOOTSTRAP_CAPACITY = 10000
DEFAULT_BOOTSTRAP_LOGGER_NAME = "Datamind.bootstrap"

# 全局 handler 实例
_bootstrap_handler: Optional[MemoryHandler] = None
_bootstrap_logger: Optional[logging.Logger] = None
_bootstrap_logger_name: Optional[str] = None
_logger_name_initialized = False

# 调试模式标志
_DEBUG_MODE = False


def set_debug_mode(enabled: bool = True):
    """设置调试模式"""
    global _DEBUG_MODE
    _DEBUG_MODE = enabled


def debug_print_cache():
    """调试打印缓存内容"""
    global _bootstrap_handler, _DEBUG_MODE

    if not _DEBUG_MODE:
        return

    print("\n" + "=" * 80)
    print("【启动日志缓存调试信息】")
    print("=" * 80)

    if not _bootstrap_handler:
        print("缓存处理器未初始化")
        print("=" * 80 + "\n")
        return

    print(f"缓存处理器状态: 已初始化")
    print(f"缓存容量: {BOOTSTRAP_CAPACITY}")
    print(f"处理器级别: {logging.getLevelName(_bootstrap_handler.level)}")

    # 检查缓冲区
    if hasattr(_bootstrap_handler, 'buffer'):
        buffer_size = len(_bootstrap_handler.buffer)
        print(f"当前缓存数量: {buffer_size} 条")

        if buffer_size > 0:
            print("\n缓存日志内容:")
            print("-" * 60)

            # 按级别统计
            level_stats: Dict[int, int] = {}

            for i, record in enumerate(_bootstrap_handler.buffer, 1):
                # 统计级别
                level_stats[record.levelno] = level_stats.get(record.levelno, 0) + 1

                # 打印日志详情
                print(f"\n  [{i}] {logging.getLevelName(record.levelno)} - {record.name}")
                print(f"      时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created))}")
                print(f"      模块: {record.module}:{record.lineno}")
                print(f"      消息: {record.getMessage()}")

                # 如果有异常信息
                if record.exc_info:
                    print(f"      异常: {record.exc_info[1]}")

            # 打印统计信息
            print("-" * 60)
            print("\n缓存统计:")
            for levelno, count in sorted(level_stats.items()):
                print(f"  {logging.getLevelName(levelno)}: {count} 条")

            print(f"\n总计: {buffer_size} 条日志")
        else:
            print("\n缓存为空，没有日志记录")
    else:
        print("无法访问缓存缓冲区")

    print("=" * 80 + "\n")


def debug_peek_cache(last_n: int = 10) -> List[Dict[str, Any]]:
    """
    查看最近的N条缓存日志

    Args:
        last_n: 要查看的最近日志数量

    Returns:
        包含日志信息的字典列表
    """
    global _bootstrap_handler

    result = []

    if not _bootstrap_handler or not hasattr(_bootstrap_handler, 'buffer'):
        return result

    buffer = _bootstrap_handler.buffer
    if not buffer:
        return result

    # 获取最近的N条
    start_idx = max(0, len(buffer) - last_n)
    for record in buffer[start_idx:]:
        log_info = {
            'level': logging.getLevelName(record.levelno),
            'levelno': record.levelno,
            'name': record.name,
            'message': record.getMessage(),
            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created)),
            'module': record.module,
            'lineno': record.lineno,
            'funcName': record.funcName,
            'created': record.created
        }

        # 如果有异常信息
        if record.exc_info:
            log_info['exception'] = str(record.exc_info[1])

        result.append(log_info)

    return result


def debug_get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        统计信息字典
    """
    global _bootstrap_handler

    stats = {
        'initialized': _bootstrap_handler is not None,
        'capacity': BOOTSTRAP_CAPACITY,
        'handler_level': None,
        'buffer_size': 0,
        'level_stats': {},
        'oldest_log': None,
        'newest_log': None
    }

    if not _bootstrap_handler or not hasattr(_bootstrap_handler, 'buffer'):
        return stats

    stats['handler_level'] = logging.getLevelName(_bootstrap_handler.level)

    buffer = _bootstrap_handler.buffer
    stats['buffer_size'] = len(buffer)

    if buffer:
        # 按级别统计
        for record in buffer:
            level = logging.getLevelName(record.levelno)
            stats['level_stats'][level] = stats['level_stats'].get(level, 0) + 1

        # 最早和最晚的日志
        oldest = buffer[0]
        newest = buffer[-1]

        stats['oldest_log'] = {
            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldest.created)),
            'level': logging.getLevelName(oldest.levelno),
            'message': oldest.getMessage()[:50] + '...' if len(oldest.getMessage()) > 50 else oldest.getMessage()
        }

        stats['newest_log'] = {
            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(newest.created)),
            'level': logging.getLevelName(newest.levelno),
            'message': newest.getMessage()[:50] + '...' if len(oldest.getMessage()) > 50 else newest.getMessage()
        }

    return stats


def get_bootstrap_logger_name() -> str:
    """获取 bootstrap logger 名称"""
    global _bootstrap_logger_name, _logger_name_initialized

    if not _logger_name_initialized:
        _bootstrap_logger_name = DEFAULT_BOOTSTRAP_LOGGER_NAME
        _logger_name_initialized = True

    return _bootstrap_logger_name


def set_bootstrap_logger_name(name: str):
    """手动设置 bootstrap logger 名称"""
    global _bootstrap_logger_name, _bootstrap_logger, _logger_name_initialized
    _bootstrap_logger_name = name
    _logger_name_initialized = True
    _bootstrap_logger = None


def install_bootstrap_logger(custom_name: Optional[str] = None):
    """
    安装启动日志缓存，必须在应用最早执行
    """
    global _bootstrap_handler, _bootstrap_logger

    # 设置 logger 名称
    if custom_name:
        set_bootstrap_logger_name(custom_name)
    else:
        get_bootstrap_logger_name()

    # 创建内存处理器
    _bootstrap_handler = MemoryHandler(
        capacity=BOOTSTRAP_CAPACITY,
        flushLevel=logging.CRITICAL,
        target=None
    )
    _bootstrap_handler.setLevel(logging.INFO)

    # 创建或获取 bootstrap logger
    _bootstrap_logger = logging.getLogger(_bootstrap_logger_name)
    _bootstrap_logger.setLevel(logging.INFO)
    _bootstrap_logger.propagate = False
    _bootstrap_logger.addHandler(_bootstrap_handler)

    # 如果处于调试模式，打印初始化信息
    if _DEBUG_MODE:
        print(f"\n启动日志缓存已初始化: {_bootstrap_logger_name}")
        print(f"容量: {BOOTSTRAP_CAPACITY}, 级别: INFO")


def flush_bootstrap_logs() -> int:
    """
    将启动日志 flush 到真正的 handler
    """
    global _bootstrap_handler, _bootstrap_logger

    if not _bootstrap_handler or not _bootstrap_logger:
        print("[Bootstrap] 错误: handler或logger未初始化")
        return 0

    flushed_count = 0

    #  从 Datamind logger 查找处理器，而不是 root logger
    from config.logging_config import LoggingConfig
    config = LoggingConfig.load_silent()  # 静默加载配置获取名称
    app_logger = logging.getLogger(config.name)  # 获取 "Datamind" logger

    print(f"\n[Bootstrap] {config.name} logger.handlers: {len(app_logger.handlers)}")
    for i, handler in enumerate(app_logger.handlers):
        print(f"  [{i}] {type(handler).__name__} - {handler.__class__}")

    # 找到真正的文件处理器
    target_handler = None
    for handler in app_logger.handlers:
        if not isinstance(handler, MemoryHandler):
            target_handler = handler
            print(f"[Bootstrap] 找到目标处理器: {type(handler).__name__}")
            break

    if not target_handler:
        print("[Bootstrap] 错误: 没有找到文件处理器")
        return 0

    # 检查缓冲区
    if hasattr(_bootstrap_handler, 'buffer'):
        buffer_size = len(_bootstrap_handler.buffer)
        print(f"[Bootstrap] 缓冲区大小: {buffer_size}")

        if buffer_size > 0:
            # 打印缓冲区内容
            print("[Bootstrap] 缓冲区内容:")
            for i, record in enumerate(_bootstrap_handler.buffer):
                print(f"  [{i}] {record.levelname} - {record.getMessage()}")

            # 设置目标处理器
            _bootstrap_handler.setTarget(target_handler)

            # 刷新所有缓存的日志
            _bootstrap_handler.flush()
            flushed_count = buffer_size
            print(f"[Bootstrap] 已调用 flush()，尝试刷新 {flushed_count} 条日志")

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
        logger_name = get_bootstrap_logger_name()
        _bootstrap_logger = logging.getLogger(logger_name)
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