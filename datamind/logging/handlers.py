# datamind/logging/handlers.py

"""日志输出通道处理器

只负责日志输出，不做任何加工逻辑。

核心功能：
  - create_file_handler: 创建文件日志 handler（支持 time/size 轮转）
  - create_console_handler: 创建控制台 handler
  - create_async_handler: 创建异步日志 handler（queue 模式）

使用示例：
  from datamind.logging.handlers import create_file_handler, create_console_handler

  file_handler = create_file_handler(config)
  console_handler = create_console_handler(formatter)
"""

import logging
from queue import Queue
from logging.handlers import (
    QueueHandler,
    QueueListener,
    TimedRotatingFileHandler,
    RotatingFileHandler,
)

from datamind.config.logging import LoggingConfig


def create_file_handler(config: LoggingConfig) -> logging.Handler:
    """创建文件日志 handler

    参数：
        config: 日志配置对象

    返回：
        文件处理器实例
    """
    path = config.dir / config.filename
    config.dir.mkdir(parents=True, exist_ok=True)

    if config.rotation == "time":
        return TimedRotatingFileHandler(
            filename=path,
            when=config.rotation_when,
            interval=config.rotation_interval,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    if config.rotation == "size":
        return RotatingFileHandler(
            filename=path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    raise ValueError(f"不支持的日志轮转策略: {config.rotation}")


def create_console_handler(formatter) -> logging.Handler:
    """创建控制台 handler

    参数：
        formatter: 日志格式化器

    返回：
        控制台处理器实例
    """
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return handler


def create_async_handler(handlers: list):
    """创建异步日志 handler（queue 模式）

    参数：
        handlers: 需要异步包装的 handler 列表

    返回：
        (queue_handler, queue_listener)
    """
    queue = Queue(-1)

    queue_handler = QueueHandler(queue)

    listener = QueueListener(
        queue,
        *handlers,
        respect_handler_level=True,
    )

    return queue_handler, listener