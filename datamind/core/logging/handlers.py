# datamind/core/logging/handlers.py

"""日志处理器

提供日志处理功能，包括时区感知的时间轮转和异步日志处理。

核心功能：
  - TimeRotatingFileHandlerWithTimezone: 支持时区的时间轮转文件处理器
  - AsyncLogHandler: 异步日志处理器，使用队列实现非阻塞日志写入

特性：
  - 时区感知：时间轮转考虑配置的时区
  - 异步处理：队列缓冲，非阻塞写入
  - 优雅关闭：确保日志完整写入
  - 降级处理：队列满时降级为同步处理
  - 统计信息：提供处理器统计

使用示例：
    from datamind.core.logging.handlers import (
        TimeRotatingFileHandlerWithTimezone,
        AsyncLogHandler
    )

    # 时区感知的时间轮转处理器
    handler = TimeRotatingFileHandlerWithTimezone(
        config=config,
        filename="app.log",
        when="midnight",
        interval=1
    )

    # 异步处理器
    async_handler = AsyncLogHandler(config, target_handler)
"""

import os
import sys
import time
import atexit
import threading
import logging.handlers
from queue import Queue, Empty, Full
from typing import Optional, Any, Dict
from datetime import time as dt_time

from datamind.config.logging_config import LoggingConfig
from datamind.core.logging.formatters import TimezoneFormatter

_logger = logging.getLogger(__name__)

# 处理器调试开关
_HANDLER_DEBUG = os.environ.get('DATAMIND_HANDLER_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """处理器内部调试输出"""
    if _HANDLER_DEBUG:
        if args:
            print(f"[Handler] {msg % args}", file=sys.stderr)
        else:
            print(f"[Handler] {msg}", file=sys.stderr)


class TimeRotatingFileHandlerWithTimezone(logging.handlers.TimedRotatingFileHandler):
    """支持时区的时间轮转处理器"""

    def __init__(self, config: LoggingConfig, *args: Any, **kwargs: Any):
        """初始化时区感知的时间轮转处理器

        参数:
            config: 日志配置对象
            *args: 父类位置参数
            **kwargs: 父类关键字参数
        """
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)

        if config.rotation_at_time:
            hour, minute = map(int, config.rotation_at_time.split(':'))
            kwargs['atTime'] = dt_time(hour, minute)

        if config.rotation_utc:
            kwargs['utc'] = True

        super().__init__(*args, **kwargs)
        _debug("TimeRotatingFileHandlerWithTimezone 已创建: %s", kwargs.get('filename', 'unknown'))


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""

    def __init__(self, config: LoggingConfig, target_handler: logging.Handler):
        """初始化异步日志处理器

        参数:
            config: 日志配置对象
            target_handler: 目标处理器
        """
        super().__init__()
        self.config = config
        self.target_handler = target_handler
        self.queue: Queue = Queue(maxsize=config.async_queue_size)
        self._stop_event: threading.Event = threading.Event()
        self._processed_count: int = 0
        self._dropped_count: int = 0
        self._worker_thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

        # 统计更新间隔（秒）
        self._stats_update_interval: float = 1

        self._start_worker()
        atexit.register(self.stop)
        _debug("AsyncLogHandler 已创建: queue_size=%d", config.async_queue_size)

    def _start_worker(self) -> None:
        """启动工作线程"""
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="AsyncLogWorker"
        )
        self._worker_thread.start()
        _debug("异步日志工作线程已启动")

    def emit(self, record: logging.LogRecord) -> None:
        """将日志记录放入队列

        参数:
            record: 日志记录对象
        """
        try:
            self.queue.put(record, timeout=0.1)
        except Full:
            with self._lock:
                self._dropped_count += 1
            _logger.warning("异步队列已满，降级为同步处理，已丢弃: %d", self._dropped_count)
            try:
                self.target_handler.handle(record)
            except Exception as handler_error:
                _logger.error("降级处理失败: %s", handler_error, exc_info=True)

    def _process_queue(self) -> None:
        """处理队列的工作线程"""
        processed_count = 0
        last_stats_time = time.time()
        stats_interval = self._stats_update_interval

        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=0.5)
                self.target_handler.emit(record)
                processed_count += 1

                # 批量处理队列中剩余记录
                self._drain_queue()

                # 定期更新统计信息到共享变量
                current_time = time.time()
                if current_time - last_stats_time >= stats_interval:
                    with self._lock:
                        self._processed_count = processed_count
                    last_stats_time = current_time

                    _debug("异步处理器统计: 已处理 %d 条日志，队列剩余: %d",
                           processed_count, self.queue.qsize())

            except Empty:
                _debug("队列为空，继续等待")
                continue
            except Exception as e:
                _logger.error("处理队列时发生异常: %s", e, exc_info=True)
                continue

        # 线程退出前处理剩余记录
        self._drain_queue(final=True)

        # 最终更新统计信息
        with self._lock:
            self._processed_count = processed_count

        _debug("异步日志工作线程退出，总共处理 %d 条日志，丢弃 %d 条",
               processed_count, self._dropped_count)

    def _drain_queue(self, final: bool = False) -> None:
        """清空队列中的剩余记录

        参数:
            final: 是否最终清空（用于区分正常清空和关闭时的清空）
        """
        remaining = 0
        while True:
            try:
                record = self.queue.get_nowait()
                self.target_handler.emit(record)
                remaining += 1
            except Empty:
                break

        if remaining > 0:
            if final:
                _debug("最终清空: 批量处理了 %d 条日志", remaining)
            else:
                _debug("批量处理了 %d 条日志", remaining)

    def stop(self, timeout: float = 2.0) -> None:
        """停止异步处理器

        参数:
            timeout: 等待工作线程退出的超时时间（秒）
        """
        _debug("停止异步日志处理器")
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                _logger.warning("异步日志工作线程未能正常退出（超时 %.1f 秒）", timeout)
            else:
                _debug("异步日志工作线程已退出")

    def close(self) -> None:
        """关闭处理器"""
        self.stop()
        super().close()

    def flush(self) -> None:
        """刷新处理器，等待队列中的日志处理完成"""
        _debug("刷新异步处理器，当前队列剩余: %d", self.queue.qsize())

        # 等待队列清空
        timeout = 5.0
        start_time = time.time()
        while not self.queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if self.queue.empty():
            _debug("队列已清空")
        else:
            _logger.warning("队列仍有 %d 条日志未处理", self.queue.qsize())

        # 刷新目标处理器
        if hasattr(self.target_handler, 'flush'):
            try:
                self.target_handler.flush()
                _debug("目标处理器已刷新")
            except Exception as e:
                _logger.error("刷新目标处理器失败: %s", e)

    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            queue_size = self.queue.qsize()
            return {
                'queue_size': queue_size,
                'max_queue_size': self.config.async_queue_size,
                'processed_count': self._processed_count,
                'dropped_count': self._dropped_count,
                'is_running': self._worker_thread is not None and self._worker_thread.is_alive(),
                'queue_usage_percent': (queue_size / self.config.async_queue_size * 100)
                if self.config.async_queue_size > 0 else 0,
            }

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._processed_count = 0
            self._dropped_count = 0
        _debug("统计信息已重置")


__all__ = [
    "TimeRotatingFileHandlerWithTimezone",
    "AsyncLogHandler",
]