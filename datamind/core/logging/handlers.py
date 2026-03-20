# Datamind/datamind/core/logging/handlers.py

"""日志处理器

提供日志处理功能：
  - TimeRotatingFileHandlerWithTimezone: 支持时区的时间轮转文件处理器
  - AsyncLogHandler: 异步日志处理器，使用队列实现非阻塞日志写入

特性：
  - 时区感知的时间轮转
  - 异步日志处理，提升性能
  - 队列缓冲，防止日志丢失
  - 优雅关闭，确保日志完整写入
"""

import time
import atexit
import threading
import logging.handlers
from queue import Queue, Empty
from typing import Optional, Any, Dict
from datetime import datetime, time as dt_time

from datamind.config import LoggingConfig
from datamind.core.logging.formatters import TimezoneFormatter
from datamind.core.logging.debug import debug_print


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

        self._debug(
            "初始化 TimeRotatingFileHandlerWithTimezone, 文件: %s, 时区: %s, 轮转时间: %s",
            kwargs.get('filename', 'unknown'),
            config.timezone.value,
            config.rotation_at_time
        )

        # 设置轮转时间，转换为 datetime.time 对象
        if config.rotation_at_time:
            hour, minute = map(int, config.rotation_at_time.split(':'))
            kwargs['atTime'] = dt_time(hour, minute)
            self._debug("设置轮转时间: %s", config.rotation_at_time)

        # 设置是否使用UTC
        if config.rotation_utc:
            kwargs['utc'] = True
            self._debug("使用UTC时间轮转")

        # 设置备份计数
        if hasattr(config, 'rotation_backup_count') and config.rotation_backup_count > 0:
            kwargs['backupCount'] = config.rotation_backup_count
            self._debug("设置备份计数: %d", config.rotation_backup_count)

        super().__init__(*args, **kwargs)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.handler_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def computeRollover(self, currentTime: float) -> float:
        """计算轮转时间（考虑时区）

        参数:
            currentTime: 当前时间戳

        返回:
            下次轮转的时间戳
        """
        dt = datetime.fromtimestamp(currentTime)
        dt_tz = self.timezone_formatter.format_time(dt)

        rollover_time = super().computeRollover(currentTime)

        self._debug(
            "计算轮转时间 - 当前时间: %s (UTC), %s (本地), 下次轮转: %s",
            dt,
            dt_tz,
            datetime.fromtimestamp(rollover_time)
        )

        return rollover_time

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """判断是否应该轮转（考虑时区）

        参数:
            record: 日志记录对象

        返回:
            是否应该轮转
        """
        result = super().shouldRollover(record)

        if result:
            current_time = time.time()
            dt = datetime.fromtimestamp(current_time)
            dt_tz = self.timezone_formatter.format_time(dt)
            self._debug("触发轮转: %s (%s)", dt, dt_tz)

        return result


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
        self._dropped_count: int = 0  # 记录丢弃的日志数
        self._worker_thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

        self._debug(
            "初始化 AsyncLogHandler, 队列大小: %d, 目标处理器: %s",
            config.async_queue_size,
            target_handler.__class__.__name__
        )

        self._start_worker()
        atexit.register(self.stop)

        self._debug("异步日志处理器启动完成")

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.handler_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _warning(self, msg: str, *args: Any) -> None:
        """警告输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.handler_debug:
            debug_print(f"{self.__class__.__name__} WARNING", msg, *args)

    def _start_worker(self) -> None:
        """启动工作线程"""
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="AsyncLogWorker"
        )
        self._worker_thread.start()
        self._debug("工作线程已启动: %s", self._worker_thread.name)

    def emit(self, record: logging.LogRecord) -> None:
        """将日志记录放入队列

        参数:
            record: 日志记录对象
        """
        try:
            # 尝试将记录放入队列
            self.queue.put(record, timeout=0.1)
            self._debug("日志记录放入队列，当前队列大小: %d/%d",
                        self.queue.qsize(), self.config.async_queue_size)
        except Exception as e:
            # 队列满，降级处理
            with self._lock:
                self._dropped_count += 1

            self._warning("异步队列已满 (%d/%d)，降级为同步处理，已丢弃: %d",
                          self.queue.qsize(), self.config.async_queue_size, self._dropped_count)
            try:
                self.target_handler.handle(record)
                self._debug("降级处理成功")
            except Exception as handler_error:
                self._debug("降级处理失败: %s", handler_error)

    def _process_queue(self) -> None:
        """处理队列的工作线程"""
        processed_count = 0
        empty_loops = 0
        last_stats_time = time.time()
        stats_interval = 60  # 每60秒输出一次统计

        self._debug("异步日志工作线程启动")

        while not self._stop_event.is_set():
            try:
                # 使用较短的超时时间，以便能及时响应停止信号
                record = self.queue.get(timeout=0.5)
                self.target_handler.emit(record)
                processed_count += 1
                empty_loops = 0

                # 尝试处理队列中剩余的所有记录（非阻塞）
                self._drain_queue(processed_count)

                # 定期输出统计信息
                current_time = time.time()
                if current_time - last_stats_time >= stats_interval:
                    self._debug("异步处理器统计: 已处理 %d 条日志，队列剩余: %d",
                                processed_count, self.queue.qsize())
                    last_stats_time = current_time

            except Empty:
                empty_loops += 1
                if empty_loops > 10 and processed_count > 0:
                    # 如果长时间没有新日志，输出统计信息
                    self._debug("队列空闲，已处理 %d 条日志", processed_count)
                    empty_loops = 0
                continue
            except Exception as e:
                self._debug("处理队列时发生异常: %s", e)
                continue

        # 线程退出前，处理完队列中剩余的所有记录
        self._drain_queue(processed_count, final=True)

        with self._lock:
            self._processed_count = processed_count

        self._debug("异步日志工作线程退出，总共处理 %d 条日志，丢弃 %d 条",
                    processed_count, self._dropped_count)

    def _drain_queue(self, processed_count: int, final: bool = False) -> None:
        """清空队列中的剩余记录

        参数:
            processed_count: 已处理计数（用于调试）
            final: 是否最终清空
        """
        remaining = 0
        batch_count = 0

        while True:
            try:
                record = self.queue.get_nowait()
                self.target_handler.emit(record)
                remaining += 1
                batch_count += 1

                # 批量处理时每100条输出一次调试信息
                if batch_count % 100 == 0:
                    self._debug("批量处理中，已处理 %d 条", batch_count)

            except Empty:
                break

        if remaining > 0:
            if final:
                self._debug("处理器退出前处理了 %d 条剩余日志", remaining)
            else:
                self._debug("批量处理了 %d 条日志，总计已处理 %d", remaining, processed_count)

    def stop(self, timeout: float = 2.0) -> None:
        """停止异步处理器

        参数:
            timeout: 等待工作线程退出的超时时间（秒）
        """
        self._debug("停止异步日志处理器，当前队列剩余: %d", self.queue.qsize())
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

            if self._worker_thread.is_alive():
                self._debug("异步日志工作线程未能正常退出（超时 %.1f 秒）", timeout)
            else:
                self._debug("异步日志处理器已停止，共处理 %d 条日志，丢弃 %d 条",
                            self._processed_count, self._dropped_count)

    def close(self) -> None:
        """关闭处理器"""
        self._debug("关闭异步日志处理器")
        self.stop()
        super().close()

    def flush(self) -> None:
        """刷新处理器，等待队列中的日志处理完成"""
        self._debug("刷新异步处理器，当前队列剩余: %d", self.queue.qsize())

        # 等待队列清空
        timeout = 5.0
        start_time = time.time()
        while not self.queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if self.queue.empty():
            self._debug("队列已清空")
        else:
            self._debug("队列仍有 %d 条日志未处理", self.queue.qsize())

        # 刷新目标处理器
        if hasattr(self.target_handler, 'flush'):
            try:
                self.target_handler.flush()
                self._debug("目标处理器已刷新")
            except Exception as e:
                self._debug("刷新目标处理器失败: %s", e)

    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            return {
                'queue_size': self.queue.qsize(),
                'max_queue_size': self.config.async_queue_size,
                'processed_count': self._processed_count,
                'dropped_count': self._dropped_count,
                'is_running': self._worker_thread is not None and self._worker_thread.is_alive(),
                'queue_usage_percent': (self.queue.qsize() / self.config.async_queue_size * 100)
                if self.config.async_queue_size > 0 else 0,
            }

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._processed_count = 0
            self._dropped_count = 0
        self._debug("统计信息已重置")