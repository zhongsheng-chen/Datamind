# core/log_manager.py
import logging
import logging.handlers
import json
import os
import sys
import socket
import re
import time
import random
import contextvars
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pythonjsonlogger import jsonlogger
from concurrent_log_handler import ConcurrentRotatingFileHandler
import traceback
import threading
from queue import Queue
import atexit
import gzip
import shutil
import pytz
import hashlib

from config.logging_config import LoggingConfig, LogFormat, LogLevel, TimeZone, TimestampPrecision

BASE_DIR = Path(
    os.getenv(
        "DATAMIND_HOME",
        Path(__file__).resolve().parent.parent
    )
).resolve()

_request_id_ctx = contextvars.ContextVar("request_id", default="-")

class TimezoneFormatter:
    """时区格式化器"""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone = self._get_timezone()

    def _get_timezone(self):
        """获取时区对象"""
        tz_map = {
            TimeZone.UTC: timezone.utc,
            TimeZone.LOCAL: None,  # 使用本地时间
            TimeZone.CST: pytz.timezone('Asia/Shanghai'),
            TimeZone.EST: pytz.timezone('US/Eastern'),
            TimeZone.PST: pytz.timezone('US/Pacific')
        }
        return tz_map.get(self.config.timezone, timezone.utc)

    def format_time(self, dt: Optional[datetime] = None) -> datetime:
        """格式化时间（应用时区和精度）"""
        if dt is None:
            dt = datetime.now(timezone.utc)

        # 应用时区
        if self.timezone:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(self.timezone)

        # 应用时间偏移
        if self.config.time_offset_hours != 0:
            dt = dt + timedelta(hours=self.config.time_offset_hours)

        return dt

    def format_timestamp(self, dt: Optional[datetime] = None) -> Union[str, float]:
        """格式化时间戳"""
        dt = self.format_time(dt)

        if self.config.json_use_epoch:
            # 返回时间戳
            timestamp = dt.timestamp()
            if self.config.json_epoch_unit == 'milliseconds':
                return timestamp * 1000
            elif self.config.json_epoch_unit == 'microseconds':
                return timestamp * 1_000_000
            elif self.config.json_epoch_unit == 'nanoseconds':
                return timestamp * 1_000_000_000
            return timestamp
        else:
            # 返回格式化的时间字符串
            fmt = self.config.get_python_date_format()
            return dt.strftime(fmt)[:23] + dt.strftime(fmt)[26:]  # 处理微秒精度

    def format_date(self, dt: Optional[datetime] = None) -> str:
        """格式化日期"""
        dt = self.format_time(dt)

        if self.config.format == LogFormat.JSON:
            fmt = self.config.json_date_format
            if 'yyyy' in fmt:
                fmt = fmt.replace('yyyy', '%Y').replace('yy', '%y')
                fmt = fmt.replace('MM', '%m').replace('dd', '%d')
        else:
            fmt = self.config.text_date_format

        return dt.strftime(fmt)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON格式化器"""
    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            json_ensure_ascii=False,
            json_indent=None
        )

    @staticmethod
    def _safe_json(obj):
        try:
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # 保留 extra
        INTERNAL_FIELDS = {
            "msg", "message", "args", "exc_info", "exc_text",
            "stack_info", "lineno", "pathname", "filename",
            "module", "funcName", "created", "msecs",
            "relativeCreated"
        }

        for key, value in record.__dict__.items():
            if key not in RESERVED_ATTRS and key not in INTERNAL_FIELDS and key not in log_record:
                log_record[key] = value
                if callable(value):
                    continue

        # trace 信息（分布式追踪）
        log_record.setdefault("trace_id", getattr(record, "trace_id", None))
        log_record.setdefault("span_id", getattr(record, "span_id", None))

        # 标准字段
        log_record.setdefault("message", record.getMessage())
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)

    def process_log_record(self, log_record):
        """处理日志记录"""

        # 获取当前时间
        now = self.timezone_formatter.format_time()

        # 添加时间字段
        log_record[self.config.json_timestamp_field] = \
            self.timezone_formatter.format_timestamp(now)

        log_record["date"] = self.timezone_formatter.format_date(now)
        log_record["timezone"] = self.config.timezone.value
        log_record["timestamp_precision"] = self.config.timestamp_precision.value

        # 添加其他标准字段
        log_record["environment"] = LoggingConfig.environment
        log_record["service"] = self.config.name
        log_record["hostname"] = socket.gethostname()

        log_record["pid"] = os.getpid()
        log_record["thread"] = threading.current_thread().name

        # 确保 request_id 字段存在
        log_record.setdefault("request_id", "-")

        # 处理异常信息
        exc_info = log_record.get("exc_info")

        if exc_info:
            try:
                if isinstance(exc_info, tuple):
                    exc_type, exc_value, exc_tb = exc_info

                    log_record["exception"] = {
                        "type": exc_type.__name__,
                        "message": str(exc_value),
                        "traceback": traceback.format_exception(
                            exc_type, exc_value, exc_tb
                        )
                    }
            except Exception:
                pass

        # 清理内部字段
        for field in ("exc_info", "exc_text", "stack_info", "args"):
            log_record.pop(field, None)

        for k, v in list(log_record.items()):
            log_record[k] = self._safe_json(v)

        return log_record


class CustomTextFormatter(logging.Formatter):
    """自定义文本格式化器"""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            fmt=config.text_format,
            datefmt=config.text_datetime_format
        )

    def formatTime(self, record, datefmt=None):
        """重写时间格式化"""
        created_time = datetime.fromtimestamp(record.created)
        formatted_time = self.timezone_formatter.format_timestamp(created_time)

        if isinstance(formatted_time, float):
            # 如果是时间戳，转换为字符串
            if self.config.timestamp_precision == TimestampPrecision.SECONDS:
                return str(int(formatted_time))
            elif self.config.timestamp_precision == TimestampPrecision.MILLISECONDS:
                return f"{formatted_time:.0f}"
            else:
                return str(formatted_time)

        return formatted_time


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


class RequestIdFilter(logging.Filter):
    """请求ID过滤器"""

    def __init__(self):
        super().__init__()

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        _request_id_ctx.set(request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        return _request_id_ctx.get()

    def filter(self, record):
        """添加 request_id 到日志记录"""
        record.request_id = self.get_request_id()
        return True


class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
        self.patterns = self._compile_patterns()

    def _compile_patterns(self):
        """编译脱敏模式"""
        patterns = {}
        for field in self.config.sensitive_fields:
            # 为每个敏感字段创建匹配模式
            patterns[field] = re.compile(
                rf'"{field}":\s*"([^"]+)"',
                re.IGNORECASE
            )
        return patterns

    def filter(self, record):

        if not self.config.mask_sensitive:
            return True

        for field in self.config.sensitive_fields:

            if hasattr(record, field):

                value = getattr(record, field)

                if isinstance(value, str):
                    setattr(
                        record,
                        field,
                        self.config.mask_char * 8
                    )

        return True


class SamplingFilter(logging.Filter):
    """日志采样过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
        self._last_log_time = {}

    def filter(self, record):
        """判断是否应该记录此日志"""
        # 错误级别以上的日志总是记录
        if record.levelno >= logging.ERROR:
            return True

        # 采样率检查
        if self.config.sampling_rate < 1.0:
            if random.random() > self.config.sampling_rate:
                return False

        # 采样间隔检查
        if self.config.sampling_interval > 0:
            logger_name = record.name
            current_time = time.time()

            if logger_name in self._last_log_time:
                if current_time - self._last_log_time[logger_name] < self.config.sampling_interval:
                    return False

            self._last_log_time[logger_name] = current_time

        return True


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


class LogManager:
    """
    日志管理器 - 统一管理所有日志（包含完整的时间处理）
    """

    _instance = None
    _lock = threading.RLock()  # 使用可重入锁

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.config: Optional[LoggingConfig] = None
            self.timezone_formatter: Optional[TimezoneFormatter] = None
            self.request_id_filter: Optional[RequestIdFilter] = None
            self.sensitive_filter: Optional[SensitiveDataFilter] = None
            self.sampling_filter: Optional[SamplingFilter] = None
            self.access_logger: Optional[logging.Logger] = None
            self.audit_logger: Optional[logging.Logger] = None
            self.performance_logger: Optional[logging.Logger] = None
            self._cleanup_thread: Optional[threading.Thread] = None
            self._stop_cleanup = threading.Event()
            self._config_digest: Optional[str] = None

    def initialize(self, config: LoggingConfig):
        """初始化日志系统"""
        if self._initialized:
            return

        with self._lock:
            # 配置预检
            validation = config.validate_all()
            if not validation['valid']:
                errors = "\n".join(validation['errors'])
                raise RuntimeError(f"日志配置验证失败:\n{errors}")

            if validation['warnings']:
                for warning in validation['warnings']:
                    logging.getLogger().warning(f"日志配置警告: {warning}")

            self.config = config
            self.timezone_formatter = TimezoneFormatter(config)
            self._config_digest = config.get_config_digest()

            # 创建日志目录
            self._create_log_directories()

            # 初始化过滤器
            self.request_id_filter = RequestIdFilter()
            self.sensitive_filter = SensitiveDataFilter(config)
            self.sampling_filter = SamplingFilter(config)

            # 初始化日志记录器
            self._init_root_logger()
            self._init_access_logger()
            self._init_audit_logger()
            self._init_performance_logger()

            # 注册清理函数
            atexit.register(self.cleanup)

            # 启动定时清理任务
            if config.archive_enabled or config.retention_days < 365:
                self._start_cleanup_scheduler()

            self._initialized = True

            # 记录启动日志
            self._log_startup_info()

    def _log_startup_info(self):
        """记录启动信息"""
        root_logger = logging.getLogger()
        root_logger.log(
            self.config.to_logging_level(),
            "日志系统初始化完成",
            extra={
                "timezone": self.config.timezone.value,
                "timestamp_precision": self.config.timestamp_precision.value,
                "log_format": self.config.format.value,
                "log_file": self.config.file,
                "config_digest": self._config_digest
            }
        )

    def _create_log_directories(self):
        """创建日志目录"""
        self.config.ensure_log_dirs()

    def _create_file_handler(
            self,
            filename: str,
            level: Union[LogLevel, int, str],
            format_type: Optional[LogFormat] = None
    ) -> logging.Handler:
        """创建文件处理器"""

        if format_type is None:
            format_type = self.config.format

        # 确保日志目录存在
        log_dir = os.path.dirname(filename)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)

        # 如果文件名包含时间戳，添加时间信息
        if self.config.file_name_timestamp:
            current_time = self.timezone_formatter.format_time()
            timestamp = current_time.strftime(self.config.file_name_datetime_format)
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{timestamp}{ext}"

        # 选择处理器类型
        if self.config.use_concurrent:
            handler = ConcurrentRotatingFileHandler(
                filename=filename,
                maxBytes=self.config.max_bytes,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding,
                lock_file_directory=self.config.concurrent_lock_dir
            )
        elif self.config.rotation_when:
            handler = TimeRotatingFileHandlerWithTimezone(
                config=self.config,
                filename=filename,
                when=self.config.rotation_when.value,
                interval=self.config.rotation_interval,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding
            )
        else:
            handler = logging.handlers.RotatingFileHandler(
                filename=filename,
                maxBytes=self.config.max_bytes,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding
            )

        # 使用配置类的方法设置日志级别
        handler.setLevel(self.config.to_logging_level(level))

        # 设置格式器
        if format_type == LogFormat.JSON:
            formatter = CustomJsonFormatter(self.config)
        else:
            formatter = CustomTextFormatter(self.config)

        handler.setFormatter(formatter)

        # 添加过滤器
        handler.addFilter(self.request_id_filter)
        handler.addFilter(self.sensitive_filter)
        handler.addFilter(self.sampling_filter)

        # 如果是异步模式，包装为异步处理器
        if self.config.use_async:
            handler = AsyncLogHandler(self.config, handler)

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            return None

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.to_logging_level(self.config.console_level))

        # 控制台使用文本格式
        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def _init_root_logger(self):
        """初始化根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.config.to_logging_level(self.config.level))

        # 清除已有的处理器
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        # 根据配置的格式添加处理器
        if self.config.format == LogFormat.TEXT:
            # 纯文本格式
            text_handler = self._create_file_handler(
                filename=self.config.file,
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(text_handler)

            # 错误日志单独文件
            if self.config.error_file:
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(error_handler)

        elif self.config.format == LogFormat.JSON:
            # 纯JSON格式
            json_handler = self._create_file_handler(
                filename=self.config.file,
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            root_logger.addHandler(json_handler)

            # 错误日志单独文件（JSON格式）
            if self.config.error_file:
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(error_handler)

        elif self.config.format == LogFormat.BOTH:
            # 同时输出两种格式
            text_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.file, 'text'),
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(text_handler)

            json_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.file, 'json'),
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            root_logger.addHandler(json_handler)

            # 错误日志
            if self.config.error_file:
                error_text_handler = self._create_file_handler(
                    filename=self._get_both_filename(self.config.error_file, 'text'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(error_text_handler)

                error_json_handler = self._create_file_handler(
                    filename=self._get_both_filename(self.config.error_file, 'json'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(error_json_handler)

        # 控制台输出
        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                root_logger.addHandler(console_handler)

        # 记录初始化完成日志
        root_logger.log(
            self.config.to_logging_level(self.config.level),
            "根日志记录器初始化完成",
            extra={
                "format": self.config.format.value,
                "handlers": len(root_logger.handlers)
            }
        )

    def _get_both_filename(self, base_filename: str, format_type: str) -> str:
        base, ext = os.path.splitext(base_filename)
        if format_type == 'text':
            suffix = self.config.text_suffix
        else:
            suffix = self.config.json_suffix
        return f"{base}.{suffix}{ext}"

    def _init_access_logger(self):
        """初始化访问日志记录器"""
        if not self.config.enable_access_log:
            return

        self.access_logger = logging.getLogger('access')
        self.access_logger.setLevel(logging.INFO)
        self.access_logger.propagate = False

        if self.config.format == LogFormat.BOTH:
            text_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.access_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.access_logger.addHandler(text_handler)

            json_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.access_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.access_logger.addHandler(json_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.access_log_file,
                level=LogLevel.INFO,
                format_type=self.config.format
            )
            self.access_logger.addHandler(handler)

        self.access_logger.log(
            logging.INFO,
            "访问日志记录器初始化完成",
            extra={"format": self.config.format.value}
        )

    def _init_audit_logger(self):
        """初始化审计日志记录器"""
        if not self.config.enable_audit_log:
            return

        self.audit_logger = logging.getLogger('audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        # 审计日志优先使用JSON格式
        if self.config.format == LogFormat.BOTH:
            json_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.audit_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.audit_logger.addHandler(json_handler)

            text_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.audit_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.audit_logger.addHandler(text_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.audit_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON  # 审计日志总是JSON
            )
            self.audit_logger.addHandler(handler)

        self.audit_logger.log(
            logging.INFO,
            "审计日志记录器初始化完成",
            extra={"format": "json"}
        )

    def _init_performance_logger(self):
        """初始化性能日志记录器"""
        if not self.config.enable_performance_log:
            return

        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        self.performance_logger.propagate = False

        # 性能日志也使用JSON格式
        if self.config.format == LogFormat.BOTH:
            json_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.performance_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.performance_logger.addHandler(json_handler)

            text_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.performance_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.performance_logger.addHandler(text_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.performance_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON  # 性能日志总是JSON
            )
            self.performance_logger.addHandler(handler)

        self.performance_logger.log(
            logging.INFO,
            "性能日志记录器初始化完成",
            extra={"format": "json"}
        )

    def _start_cleanup_scheduler(self):
        """启动定时清理任务"""
        def cleanup_job():
            while not self._stop_cleanup.wait(self._get_seconds_to_next_cleanup()):
                try:
                    self._cleanup_old_logs()
                except Exception as e:
                    logging.getLogger().error(f"清理任务执行失败: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        self._cleanup_thread.start()

    def _get_seconds_to_next_cleanup(self) -> float:
        """计算到下次清理时间的秒数"""
        now = datetime.now()
        cleanup_hour, cleanup_minute = map(int, self.config.cleanup_at_time.split(':'))
        cleanup_time = now.replace(
            hour=cleanup_hour,
            minute=cleanup_minute,
            second=0,
            microsecond=0
        )

        if cleanup_time <= now:
            cleanup_time += timedelta(days=1)

        return (cleanup_time - now).total_seconds()

    def _cleanup_old_logs(self):
        """清理旧日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            cutoff_timestamp = cutoff_date.timestamp()

            # 收集所有日志文件
            log_files = [
                self.config.file,
                self.config.error_file,
                self.config.access_log_file,
                self.config.audit_log_file,
                self.config.performance_log_file
            ]

            # 如果是BOTH格式，还需要清理对应的text和json文件
            if self.config.format == LogFormat.BOTH:
                extended_files = []
                for f in log_files:
                    if f:
                        extended_files.append(self._get_both_filename(f, 'text'))
                        extended_files.append(self._get_both_filename(f, 'json'))
                log_files.extend(extended_files)

            for log_file in log_files:
                if not log_file or not os.path.exists(log_file):
                    continue

                # 检查并删除轮转的旧日志文件
                log_dir = os.path.dirname(log_file)
                log_name = os.path.basename(log_file)

                if not os.path.exists(log_dir):
                    continue

                for f in os.listdir(log_dir):
                    if f.startswith(log_name + ".") and f != log_name:
                        file_path = os.path.join(log_dir, f)
                        if os.path.isfile(file_path):
                            file_mtime = os.path.getmtime(file_path)

                            if file_mtime < cutoff_timestamp:
                                if self.config.archive_enabled:
                                    self._archive_file(file_path)
                                else:
                                    os.remove(file_path)
                                    logging.getLogger().info(f"删除旧日志文件: {file_path}")

        except Exception as e:
            logging.getLogger().error(f"日志清理失败: {e}")

    def _archive_file(self, file_path: str):
        """归档文件"""
        temp_path = None
        try:
            # 先复制到临时文件
            temp_path = file_path + '.tmp'
            shutil.copy2(file_path, temp_path)

            # 创建归档目录
            current_time = self.timezone_formatter.format_time()
            date_str = current_time.strftime(self.config.file_name_date_format)
            archive_subdir = os.path.join(
                self.config.archive_path,
                date_str
            )
            Path(archive_subdir).mkdir(parents=True, exist_ok=True)

            # 生成归档文件名
            base_name = os.path.basename(file_path)
            timestamp = current_time.strftime(self.config.archive_name_format)
            archive_name = f"{base_name}.{timestamp}.{self.config.archive_compression}"
            archive_path = os.path.join(archive_subdir, archive_name)

            # 压缩归档
            with open(temp_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # 删除原文件和临时文件
            os.remove(file_path)
            os.remove(temp_path)

            logging.getLogger().info(f"日志归档成功: {file_path} -> {archive_path}")

        except Exception as e:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            logging.getLogger().error(f"日志归档失败 {file_path}: {e}")

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        if self.request_id_filter:
            self.request_id_filter.set_request_id(request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        if self.request_id_filter:
            return self.request_id_filter.get_request_id()
        return '-'

    def get_current_time(self) -> datetime:
        """获取当前时间（已应用时区）"""
        if self.timezone_formatter:
            return self.timezone_formatter.format_time()
        return datetime.now()

    def log_access(self, **kwargs):
        """记录访问日志"""
        if hasattr(self, 'access_logger') and self.access_logger:
            # 创建一个包含所有字段的字典
            log_data = {
                'method': kwargs.get('method'),
                'path': kwargs.get('path'),
                'status': kwargs.get('status'),
                'duration_ms': kwargs.get('duration_ms'),
                'ip': kwargs.get('ip'),
                'user_agent': kwargs.get('user_agent'),
            }
            # 移除 None 值
            log_data = {k: v for k, v in log_data.items() if v is not None}
            # 添加其他自定义字段
            log_data.update({k: v for k, v in kwargs.items() if k not in log_data})

            # 使用 info 级别记录，将数据放在 extra 中
            self.access_logger.info("访问日志", extra=log_data)

    def log_audit(self, action: str, user_id: str, **kwargs):
        """记录审计日志"""
        if hasattr(self, 'audit_logger') and self.audit_logger:
            log_data = {
                'action': action,
                'user_id': user_id,
                'date': self.timezone_formatter.format_date(),
                **kwargs
            }
            self.audit_logger.info("审计日志", extra=log_data)

    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """记录性能日志"""
        if hasattr(self, 'performance_logger') and self.performance_logger:
            log_data = {
                'operation': operation,
                'duration_ms': duration_ms,
                **kwargs
            }
            self.performance_logger.info("性能日志", extra=log_data)

    def reload_config(self, new_config: Optional[LoggingConfig] = None) -> bool:
        """
        热重载日志配置

        Args:
            new_config: 新的配置对象，如果为None则使用当前配置的reload()方法

        Returns:
            bool: 重载是否成功
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("日志管理器尚未初始化，请先调用 initialize()")

            # 保存旧配置和状态
            old_config = self.config
            old_handlers = self._capture_current_handlers()

            try:
                # 获取新配置
                if new_config is None:
                    new_config = old_config.reload()

                # 检查配置是否有变化
                if old_config.is_equivalent_to(new_config):
                    logging.getLogger().info("配置无变化，跳过重载")
                    return True

                # 配置预检
                validation = new_config.validate_all()
                if not validation['valid']:
                    errors = "\n".join(validation['errors'])
                    raise RuntimeError(f"新配置验证失败:\n{errors}")

                # 记录重载开始
                self._log_reload_start(new_config)

                # 执行重载
                self._apply_new_config(new_config)

                # 清理旧资源
                self._cleanup_old_handlers(old_handlers)

                # 记录重载成功
                self._log_reload_success()

                return True

            except Exception as e:
                # 重载失败，回滚到旧配置
                self._rollback_config(old_config, old_handlers, e)
                raise

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器"""
        handlers = {}
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
        return handlers

    def _log_reload_start(self, new_config: LoggingConfig):
        """记录重载开始"""
        logger = logging.getLogger()
        logger.log(
            logging.INFO,
            "开始热重载日志配置",
            extra={
                "old_timezone": self.config.timezone.value,
                "new_timezone": new_config.timezone.value,
                "old_format": self.config.format.value,
                "new_format": new_config.format.value,
                "old_digest": self._config_digest,
                "new_digest": new_config.get_config_digest(),
                "event": "config_reload_start"
            }
        )

    def _apply_new_config(self, new_config: LoggingConfig):
        """应用新配置"""
        # 临时保存请求ID过滤器（因为它是线程局部变量，需要保留）
        request_id_filter = self.request_id_filter

        # 重新初始化
        self._initialized = False
        self.config = new_config
        self.timezone_formatter = TimezoneFormatter(new_config)
        self._config_digest = new_config.get_config_digest()

        # 重新创建过滤器（保留旧的请求ID过滤器）
        self.sensitive_filter = SensitiveDataFilter(new_config)
        self.sampling_filter = SamplingFilter(new_config)
        self.request_id_filter = request_id_filter  # 重用旧的

        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            for h in logger.handlers[:]:
                logger.removeHandler(h)

        # 重新初始化所有日志器
        self._init_root_logger()
        self._init_access_logger()
        self._init_audit_logger()
        self._init_performance_logger()

        self._initialized = True

    def _cleanup_old_handlers(self, old_handlers: Dict[str, List[logging.Handler]]):
        """清理旧的处理器"""
        for logger_name, handlers in old_handlers.items():
            for handler in handlers:
                try:
                    if hasattr(handler, 'stop'):
                        handler.stop()
                    handler.close()
                except Exception as e:
                    logging.getLogger().debug(f"关闭处理器失败 {handler}: {e}")

    def _rollback_config(self, old_config: LoggingConfig, old_handlers: Dict[str, List[logging.Handler]],
                         error: Exception):
        """回滚到旧配置"""
        try:
            # 清理部分初始化的新处理器
            for logger_name in ['', 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                    except:
                        pass
                    logger.removeHandler(handler)

            # 恢复旧处理器
            for logger_name, handlers in old_handlers.items():
                logger = logging.getLogger(logger_name)
                for handler in handlers:
                    logger.addHandler(handler)

            # 恢复旧配置
            self.config = old_config
            self.timezone_formatter = TimezoneFormatter(old_config)
            self._config_digest = old_config.get_config_digest()
            self._initialized = True

            # 记录回滚
            logging.getLogger().error(
                f"配置重载失败，已回滚: {error}",
                exc_info=True,
                extra={"event": "config_reload_failed"}
            )
        except Exception as rollback_error:
            # 回滚也失败了，记录严重错误
            logging.getLogger().critical(
                f"配置回滚失败，日志系统可能处于不一致状态: {rollback_error}",
                exc_info=True
            )

    def _log_reload_success(self):
        """记录重载成功"""
        logging.getLogger().info(
            "日志配置热重载成功",
            extra={
                "timezone": self.config.timezone.value,
                "format": self.config.format.value,
                "config_digest": self._config_digest,
                "event": "config_reload_success"
            }
        )

    def watch_config_changes(self, interval: int = 5) -> threading.Thread:
        """
        监控配置文件变化并自动重载

        Args:
            interval: 检查间隔（秒）

        Returns:
            监控线程
        """
        def watch_worker():
            last_mtimes = {}
            last_digest = self._config_digest

            # 获取所有相关的配置文件
            env_files = self.config.get_env_files()

            # 初始化文件修改时间
            for env_file in env_files:
                try:
                    last_mtimes[env_file] = Path(env_file).stat().st_mtime
                except:
                    pass

            while self._initialized:
                try:
                    time.sleep(interval)

                    need_reload = False
                    changed_files = []

                    # 检查文件修改时间
                    for env_file in env_files:
                        try:
                            current_mtime = Path(env_file).stat().st_mtime
                            if env_file in last_mtimes and current_mtime > last_mtimes[env_file]:
                                need_reload = True
                                changed_files.append(env_file)
                            last_mtimes[env_file] = current_mtime
                        except:
                            pass

                    if need_reload:
                        logging.getLogger().info(f"检测到配置文件变化: {changed_files}")
                        self.reload_config()

                except Exception as e:
                    logging.getLogger().error(f"配置监控失败: {e}")

        # 启动监控线程
        watcher = threading.Thread(target=watch_worker, daemon=True, name="ConfigWatcher")
        watcher.start()
        return watcher

    def cleanup(self):
        """清理资源"""
        with self._lock:
            # 停止清理线程
            if hasattr(self, '_stop_cleanup'):
                self._stop_cleanup.set()

            # 关闭所有处理器
            for logger_name in ['', 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                        logger.removeHandler(handler)
                    except Exception as e:
                        print(f"关闭处理器失败: {e}")

            self._initialized = False


# 全局日志管理器实例
log_manager = LogManager()