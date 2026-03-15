# core/logging/handlers.py

import sys
import atexit
import threading
import logging.handlers
from queue import Queue, Empty  # 添加 Empty 导入
from datetime import datetime
from config.logging_config import LoggingConfig
from core.logging.formatters import TimezoneFormatter
from core.logging.debug import debug_print



class TimeRotatingFileHandlerWithTimezone(logging.handlers.TimedRotatingFileHandler):
    """支持时区的时间轮转处理器"""

    def __init__(self, config: LoggingConfig, *args, **kwargs):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)

        self._debug(
            "初始化 TimeRotatingFileHandlerWithTimezone, 文件: %s, 时区: %s, 轮转时间: %s",
            kwargs.get('filename', 'unknown'),
            config.timezone.value,
            config.rotation_at_time
        )

        # 设置轮转时间 - 需要转换为 datetime.time 对象
        if config.rotation_at_time:
            # 解析时间字符串 "HH:MM" 为 datetime.time 对象
            hour, minute = map(int, config.rotation_at_time.split(':'))
            from datetime import time as dt_time
            kwargs['atTime'] = dt_time(hour, minute)
            self._debug("设置轮转时间: %s", config.rotation_at_time)

        if config.rotation_utc:
            kwargs['utc'] = True
            self._debug("使用UTC时间轮转")

        super().__init__(*args, **kwargs)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.handler_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def computeRollover(self, currentTime):
        """计算轮转时间（考虑时区）"""
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


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""

    def __init__(self, config: LoggingConfig, target_handler: logging.Handler):
        super().__init__()
        self.config = config
        self.target_handler = target_handler
        self.queue = Queue(maxsize=config.async_queue_size)
        self._stop_event = threading.Event()
        self._processed_count = 0  # 添加计数器用于统计

        self._debug(
            "初始化 AsyncLogHandler, 队列大小: %d, 目标处理器: %s",
            config.async_queue_size,
            target_handler.__class__.__name__
        )

        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True, name="AsyncLogWorker")
        self._worker_thread.start()
        atexit.register(self.stop)

        self._debug("异步日志处理器启动完成，工作线程: %s", self._worker_thread.name)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.handler_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _warning(self, msg, *args):
        """警告输出"""
        if self.config and self.config.handler_debug:
            debug_print(f"{self.__class__.__name__} WARNING", msg, *args)

    def emit(self, record):
        """将日志记录放入队列"""
        try:
            self.queue.put(record, timeout=0.1)
            self._debug("日志记录放入队列，当前队列大小: %d", self.queue.qsize())
        except Exception as e:
            # 队列满，降级处理
            self._warning("异步队列已满 (%d条)，降级为同步处理: %s", self.queue.qsize(), e)
            try:
                self.target_handler.handle(record)
                self._debug("降级处理成功")
            except Exception as handler_error:
                self._debug("降级处理失败: %s", handler_error)

    def _process_queue(self):
        """处理队列的工作线程"""
        processed_count = 0
        empty_count = 0
        self._debug("异步日志工作线程启动")

        while not self._stop_event.is_set():
            try:
                # 使用较短的超时时间，以便能及时响应停止信号
                record = self.queue.get(timeout=0.5)
                self.target_handler.emit(record)
                processed_count += 1
                empty_count = 0  # 重置空计数

                # 尝试处理队列中剩余的所有记录（非阻塞）
                while True:
                    try:
                        record = self.queue.get_nowait()
                        self.target_handler.emit(record)
                        processed_count += 1
                    except Empty:  # 使用 Empty 异常
                        break

                if processed_count % 100 == 0:  # 每处理100条记录输出一次
                    self._debug("异步处理器已处理 %d 条日志记录", processed_count)

            except Empty:  # 队列为空，继续循环
                empty_count += 1
                if empty_count > 10 and processed_count > 0:
                    # 如果长时间没有新日志，输出统计信息
                    self._debug("队列空闲，已处理 %d 条日志", processed_count)
                    empty_count = 0
                continue
            except Exception as e:
                # 其他异常，继续循环
                self._debug("处理队列时发生异常: %s", e)
                continue

        # 线程退出前，处理完队列中剩余的所有记录
        remaining = 0
        while True:
            try:
                record = self.queue.get_nowait()
                self.target_handler.emit(record)
                remaining += 1
            except Empty:
                break

        if remaining > 0:
            self._debug("异步处理器退出前处理了 %d 条剩余日志", remaining)

        self._processed_count = processed_count
        self._debug("异步日志工作线程退出，总共处理 %d 条日志", processed_count)

    def stop(self):
        """停止异步处理器"""
        self._debug("停止异步日志处理器，当前队列剩余: %d", self.queue.qsize())
        self._stop_event.set()
        self._worker_thread.join(timeout=2)

        if self._worker_thread.is_alive():
            self._debug("异步日志工作线程未能正常退出")
        else:
            self._debug("异步日志处理器已停止，共处理 %d 条日志", self._processed_count)

    def close(self):
        """关闭处理器"""
        self._debug("关闭异步日志处理器")
        self.stop()
        super().close()