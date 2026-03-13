# core/logging/handlers.py
import atexit
import threading
import logging.handlers
from datetime import datetime
from queue import Queue

from config.logging_config import LoggingConfig
from core.logging.formatters import TimezoneFormatter


class TimeRotatingFileHandlerWithTimezone(logging.handlers.TimedRotatingFileHandler):
    """支持时区的时间轮转处理器"""

    def __init__(self, config: LoggingConfig, *args, **kwargs):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)

        # 设置轮转时间 - 需要转换为 datetime.time 对象
        if config.rotation_at_time:
            # 解析时间字符串 "HH:MM" 为 datetime.time 对象
            hour, minute = map(int, config.rotation_at_time.split(':'))
            from datetime import time as dt_time
            kwargs['atTime'] = dt_time(hour, minute)

        if config.rotation_utc:
            kwargs['utc'] = True

        super().__init__(*args, **kwargs)

    def computeRollover(self, currentTime):
        """计算轮转时间（考虑时区）"""
        if self.config.rotation_utc:
            return super().computeRollover(currentTime)

        # 使用配置的时区计算
        dt = datetime.fromtimestamp(currentTime)
        dt_tz = self.timezone_formatter.format_time(dt)
        # 使用原始时间戳，因为基类方法期望的是时间戳
        return super().computeRollover(currentTime)


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""

    def __init__(self, config: LoggingConfig, target_handler: logging.Handler):
        super().__init__()
        self.config = config
        self.target_handler = target_handler
        self.queue = Queue(maxsize=config.async_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        atexit.register(self.stop)

    def emit(self, record):
        """将日志记录放入队列"""
        try:
            self.queue.put(record, timeout=0.1)
        except Exception:
            # 队列满，降级处理
            try:
                self.target_handler.handle(record)
            except Exception:
                pass

    def _process_queue(self):
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=0.5)
                self.target_handler.emit(record)

                while True:
                    try:
                        record = self.queue.get_nowait()
                        self.target_handler.emit(record)
                    except:
                        break

            except:
                continue

    def stop(self):
        """停止异步处理器"""
        self._stop_event.set()
        self._worker_thread.join(timeout=2)