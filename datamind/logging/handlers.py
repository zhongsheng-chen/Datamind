"""日志输出通道处理器.

只负责日志输出，不包含日志加工逻辑。

核心功能：
  - create_file_handler: 创建支持多进程并发轮转的文件日志 handler
  - create_console_handler: 创建控制台日志 handler
  - create_async_handler: 创建基于队列的异步日志 handler

使用示例：
  from datamind.logging.handlers import (
      create_async_handler,
      create_console_handler,
      create_file_handler,
  )

  file_handler = create_file_handler(
      config
  )
  console_handler = create_console_handler(
      formatter
  )

  queue_handler, listener = create_async_handler(
      [
          console_handler,
          file_handler,
      ]
  )
"""

import logging
from copy import copy
import sys
from logging.handlers import (
    QueueHandler,
    QueueListener,
)
from queue import Queue

from concurrent_log_handler import (
    ConcurrentRotatingFileHandler,
    ConcurrentTimedRotatingFileHandler,
)

from datamind.config.logging import LoggingConfig
from datamind.constants import RotationType


def create_file_handler(config: LoggingConfig) -> logging.Handler:
    """创建文件日志 handler.

    参数：
        config: 日志配置对象

    返回：
        文件日志 handler

    异常：
        ValueError: 日志轮转策略不受支持
    """
    path = config.dir / config.filename
    config.dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if config.rotation == RotationType.TIME:
        return ConcurrentTimedRotatingFileHandler(
            filename=path,
            when=str(config.rotation_when),
            interval=config.rotation_interval,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    if config.rotation == RotationType.SIZE:
        return ConcurrentRotatingFileHandler(
            filename=path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    raise ValueError(
        "不支持的日志轮转策略："
        f"{config.rotation}"
    )


def create_console_handler(
        formatter: logging.Formatter,
) -> logging.Handler:
    """创建控制台日志 handler.

    参数：
        formatter: 日志格式化器

    返回：
        控制台日志 handler
    """
    stream = sys.stdout
    original_stream = sys.__stdout__
    celery_log = sys.modules.get("celery.utils.log")

    if (
            celery_log is not None
            and original_stream is not None
            and isinstance(stream, celery_log.LoggingProxy)
    ):
        # 使用原始输出流，避免 Celery LoggingProxy 将已格式化的日志再次记录。
        stream = original_stream

    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        formatter
    )

    return handler


def create_async_handler(
        handlers: list[logging.Handler],
) -> tuple[QueueHandler, QueueListener]:
    """创建基于队列的异步日志 handler.

    参数：
        handlers: 负责实际输出的日志 handler 列表

    返回：
        队列 handler 和队列监听器
    """
    log_queue: Queue[logging.LogRecord] = Queue()

    queue_handler = _PreservingQueueHandler(log_queue)
    listener = QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True,
    )

    return queue_handler, listener


class _PreservingQueueHandler(QueueHandler):
    """同进程队列不提前格式化记录，保留多行消息、参数与异常."""

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """复制记录供异步消费，不清空 exc_info/stack_info/args."""
        return copy(record)
