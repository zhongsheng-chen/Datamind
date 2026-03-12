import logging
import logging.handlers
import json
import os
import sys
import re
import time
import random
from typing import Dict, Any, Optional, Union
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

from config.logging_config import LoggingConfig, LogFormat, LogLevel, TimeZone, TimestampPrecision


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
            dt = datetime.now()

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

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)

        fmt = config.json_format if isinstance(config.json_format, str) else None
        super().__init__(fmt)

    def process_log_record(self, log_record):
        """处理日志记录"""
        # 获取当前时间
        now = datetime.now()

        # 格式化时间
        timestamp = self.timezone_formatter.format_timestamp(now)
        date = self.timezone_formatter.format_date(now)

        # 添加时间字段
        log_record[self.config.json_timestamp_field] = timestamp
        log_record['date'] = date
        log_record['timezone'] = self.config.timezone.value
        log_record['timestamp_precision'] = self.config.timestamp_precision.value

        # 添加其他标准字段
        log_record['environment'] = os.getenv('ENVIRONMENT', 'production')
        log_record['service'] = 'datamind'
        log_record['hostname'] = os.getenv('HOSTNAME', 'localhost')
        log_record['pid'] = os.getpid()
        log_record['thread'] = threading.current_thread().name

        # 处理异常信息
        if 'exc_info' in log_record and log_record['exc_info']:
            if isinstance(log_record['exc_info'], tuple):
                log_record['exception'] = {
                    'type': log_record['exc_info'][0].__name__,
                    'message': str(log_record['exc_info'][1]),
                    'traceback': traceback.format_exception(*log_record['exc_info'])
                }
            del log_record['exc_info']

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

        # 设置轮转时间
        if config.rotation_at_time:
            kwargs['atTime'] = self._parse_time(config.rotation_at_time)

        if config.rotation_utc:
            kwargs['utc'] = True

        super().__init__(*args, **kwargs)

    def _parse_time(self, time_str: str) -> time.struct_time:
        """解析时间字符串"""
        hour, minute = map(int, time_str.split(':'))
        return time.struct_time((0, 0, 0, hour, minute, 0, 0, 0, 0))

    def computeRollover(self, currentTime):
        """计算轮转时间（考虑时区）"""
        if self.config.rotation_utc:
            return super().computeRollover(currentTime)

        # 使用配置的时区计算
        dt = datetime.fromtimestamp(currentTime)
        dt_tz = self.timezone_formatter.format_time(dt)
        return super().computeRollover(dt_tz.timestamp())


class RequestIdFilter(logging.Filter):
    """请求ID过滤器"""

    def __init__(self):
        super().__init__()
        self._local = threading.local()

    def set_request_id(self, request_id: str):
        """设置当前线程的请求ID"""
        self._local.request_id = request_id

    def get_request_id(self) -> str:
        """获取当前线程的请求ID"""
        return getattr(self._local, 'request_id', '-')

    def filter(self, record):
        """添加request_id到日志记录"""
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
        """过滤敏感信息"""
        if not self.config.mask_sensitive:
            return True

        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for field, pattern in self.patterns.items():
                record.msg = pattern.sub(
                    f'"{field}": "{self.config.mask_char * 8}"',
                    record.msg
                )

        return True


class SamplingFilter(logging.Filter):
    """日志采样过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
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


class LogManager:
    """
    日志管理器 - 统一管理所有日志（包含完整的时间处理）
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.timezone_formatter = None

    def _get_log_level(self, level_input: Union[LogLevel, int, str, None]) -> int:
        """
        统一的日志级别转换方法

        将多种格式的日志级别输入转换为标准的 logging 级别整数

        Args:
            level_input: 可以是 LogLevel 枚举、整数、字符串或 None

        Returns:
            int: 标准的 logging 级别（如 logging.INFO = 20）
        """
        if level_input is None:
            return logging.INFO

        if isinstance(level_input, LogLevel):
            # LogLevel 枚举
            return getattr(logging, level_input.value)
        elif isinstance(level_input, int):
            # 整数（如 logging.DEBUG = 10）
            return level_input
        elif isinstance(level_input, str):
            # 字符串（如 "DEBUG"）
            return getattr(logging, level_input.upper())
        else:
            # 未知类型，返回默认值
            return logging.INFO

    def initialize(self, config: LoggingConfig):
        """初始化日志系统"""
        if self._initialized:
            return

        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)

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
        self._start_cleanup_scheduler()

        self._initialized = True

        # 记录启动日志
        self._log_startup_info()

    def _log_startup_info(self):
        """记录启动信息"""
        root_logger = logging.getLogger()
        root_logger.log(
            self._get_log_level(self.config.level),
            "日志系统初始化完成",
            extra={
                "timezone": self.config.timezone.value if hasattr(self.config.timezone,
                                                                  'value') else self.config.timezone,
                "timestamp_precision": self.config.timestamp_precision.value if hasattr(self.config.timestamp_precision,
                                                                                        'value') else self.config.timestamp_precision,
                "log_format": self.config.format.value if hasattr(self.config.format, 'value') else self.config.format,
                "log_file": self.config.file
            }
        )

    def _create_log_directories(self):
        """创建日志目录"""
        current_time = self.timezone_formatter.format_time()
        date_str = current_time.strftime(self.config.file_name_date_format)

        log_dirs = [
            os.path.dirname(self.config.file),
            os.path.dirname(self.config.error_file) if self.config.error_file else None,
            os.path.dirname(self.config.access_log_file) if self.config.enable_access_log else None,
            os.path.dirname(self.config.audit_log_file) if self.config.enable_audit_log else None,
            os.path.dirname(self.config.performance_log_file) if self.config.enable_performance_log else None,
            self.config.concurrent_lock_dir if self.config.use_concurrent else None,
            os.path.join(self.config.archive_path, date_str) if self.config.archive_enabled else None
        ]

        for dir_path in log_dirs:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)

    def _create_file_handler(
            self,
            filename: str,
            level: Union[str, int, LogLevel],
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

        # 使用统一的方法设置日志级别
        handler.setLevel(self._get_log_level(level))

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

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            return None

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self._get_log_level(self.config.console_level))

        # 控制台使用文本格式
        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def _init_root_logger(self):
        """初始化根日志记录器"""
        root_logger = logging.getLogger()

        # 使用统一的方法设置日志级别
        root_logger.setLevel(self._get_log_level(self.config.level))

        # 清除已有的处理器
        root_logger.handlers.clear()

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

            # 1. 文本格式处理器（主日志）
            text_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.file, 'text'),
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(text_handler)

            # 2. JSON格式处理器（主日志）
            json_handler = self._create_file_handler(
                filename=self._get_both_filename(self.config.file, 'json'),
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            root_logger.addHandler(json_handler)

            # 3. 错误日志 - 文本格式
            if self.config.error_file:
                error_text_handler = self._create_file_handler(
                    filename=self._get_both_filename(self.config.error_file, 'text'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(error_text_handler)

                # 错误日志 - JSON格式
                error_json_handler = self._create_file_handler(
                    filename=self._get_both_filename(self.config.error_file, 'json'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(error_json_handler)

        # 控制台输出（所有格式都支持控制台）
        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                root_logger.addHandler(console_handler)

        # 记录初始化完成日志
        root_logger.log(
            self._get_log_level(self.config.level),
            "根日志记录器初始化完成",
            extra={
                "format": self.config.format.value if hasattr(self.config.format, 'value') else self.config.format,
                "handlers": len(root_logger.handlers)
            }
        )

    def _get_both_filename(self, base_filename: str, suffix: str) -> str:
        """获取BOTH格式的文件名"""
        base, ext = os.path.splitext(base_filename)
        return f"{base}.{suffix}{ext}"

    def _init_access_logger(self):
        """初始化访问日志记录器 - 支持三种格式"""
        if not self.config.enable_access_log:
            return

        self.access_logger = logging.getLogger('access')
        self.access_logger.setLevel(logging.INFO)
        self.access_logger.propagate = False

        if self.config.format == LogFormat.BOTH:
            # 同时输出两种格式
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
            # 单一格式
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
        """初始化审计日志记录器 - 支持三种格式"""
        if not self.config.enable_audit_log:
            return

        self.audit_logger = logging.getLogger('audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        # 审计日志强制使用JSON格式用于分析，但可以根据配置决定是否同时输出文本
        if self.config.format == LogFormat.BOTH:
            # 同时输出两种格式，JSON用于分析，文本用于备份
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
        elif self.config.format == LogFormat.JSON:
            # 只输出JSON
            handler = self._create_file_handler(
                filename=self.config.audit_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.audit_logger.addHandler(handler)
        else:  # TEXT格式
            # 即使是TEXT格式，审计日志也建议用JSON，但尊重配置
            handler = self._create_file_handler(
                filename=self.config.audit_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.audit_logger.addHandler(handler)

        self.audit_logger.log(
            logging.INFO,
            "审计日志记录器初始化完成",
            extra={"format": self.config.format.value}
        )

    def _init_performance_logger(self):
        """初始化性能日志记录器 - 支持三种格式"""
        if not self.config.enable_performance_log:
            return

        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        self.performance_logger.propagate = False

        # 性能日志通常也使用JSON格式便于分析
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
        elif self.config.format == LogFormat.JSON:
            handler = self._create_file_handler(
                filename=self.config.performance_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.performance_logger.addHandler(handler)
        else:  # TEXT格式
            handler = self._create_file_handler(
                filename=self.config.performance_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.performance_logger.addHandler(handler)

        self.performance_logger.log(
            logging.INFO,
            "性能日志记录器初始化完成",
            extra={"format": self.config.format.value}
        )

    def _start_cleanup_scheduler(self):
        """启动定时清理任务"""

        def cleanup_job():
            while True:
                try:
                    # 计算到下次清理时间的等待时间
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

                    wait_seconds = (cleanup_time - now).total_seconds()
                    time.sleep(wait_seconds)

                    # 执行清理
                    self._cleanup_old_logs()

                except Exception as e:
                    logging.error(f"清理任务执行失败: {e}")

        cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        cleanup_thread.start()

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
                    if f.startswith(log_name) and f != log_name:
                        file_path = os.path.join(log_dir, f)
                        if os.path.isfile(file_path):
                            file_mtime = os.path.getmtime(file_path)

                            if file_mtime < cutoff_timestamp:
                                if self.config.archive_enabled:
                                    self._archive_file(file_path)
                                else:
                                    os.remove(file_path)
                                    logging.info(f"删除旧日志文件: {file_path}")

        except Exception as e:
            logging.error(f"日志清理失败: {e}")

    def _archive_file(self, file_path: str):
        """归档文件"""
        try:
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
            with open(file_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # 删除原文件
            os.remove(file_path)

            logging.info(f"日志归档成功: {file_path} -> {archive_path}")

        except Exception as e:
            logging.error(f"日志归档失败 {file_path}: {e}")

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        self.request_id_filter.set_request_id(request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        return self.request_id_filter.get_request_id()

    def get_current_time(self) -> datetime:
        """获取当前时间（已应用时区）"""
        return self.timezone_formatter.format_time()

    def log_access(self, **kwargs):
        """记录访问日志"""
        if hasattr(self, 'access_logger'):
            extra = {
                'timestamp': self.timezone_formatter.format_timestamp(),
                **kwargs
            }
            self.access_logger.log(logging.INFO, "", extra=extra)

    def log_audit(self, action: str, user_id: str, **kwargs):
        """记录审计日志"""
        if hasattr(self, 'audit_logger'):
            extra = {
                'action': action,
                'user_id': user_id,
                'timestamp': self.timezone_formatter.format_timestamp(),
                'date': self.timezone_formatter.format_date(),
                **kwargs
            }
            self.audit_logger.log(logging.INFO, "", extra=extra)

    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """记录性能日志"""
        if hasattr(self, 'performance_logger'):
            extra = {
                'operation': operation,
                'duration_ms': duration_ms,
                'timestamp': self.timezone_formatter.format_timestamp(),
                **kwargs
            }
            self.performance_logger.log(logging.INFO, "", extra=extra)

    def cleanup(self):
        """清理资源"""
        # 关闭所有处理器
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


# 全局日志管理器实例
log_manager = LogManager()