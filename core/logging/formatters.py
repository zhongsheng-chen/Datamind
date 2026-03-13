# core/logging/formatters.py
import os
import json
import pytz
import socket
import traceback
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Union
from pythonjsonlogger import jsonlogger
from config.logging_config import LoggingConfig, LogFormat, TimeZone, TimestampPrecision

# 获取 bootstrap logger 用于调试
_bootstrap_logger = logging.getLogger("datamind.bootstrap")


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

    # 获取LogRecord的所有保留属性
    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            json_ensure_ascii=False,
            json_indent=None
        )

    def _debug(self, msg, *args):
        """调试输出，使用 bootstrap logger"""
        if self.config.formatter_debug:
            _bootstrap_logger.debug(f"[CustomJsonFormatter] {msg}", *args)

    def _safe_json(self, obj):
        """安全地将对象转换为JSON可序列化格式"""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Exception):
            return str(obj)
        if isinstance(obj, (list, tuple)):
            return [self._safe_json(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): self._safe_json(v) for k, v in obj.items()}
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)

    def add_fields(self, log_record, record, message_dict):
        # 先调用父类方法
        super().add_fields(log_record, record, message_dict)

        # 添加基本字段
        log_record.setdefault('level', record.levelname)
        log_record.setdefault('logger', record.name)
        log_record.setdefault('message', record.getMessage())

        # 添加所有 extra 字段
        for key, value in record.__dict__.items():
            # 如果不是保留属性、不是私有属性、且还未在log_record中
            if (key not in self.RESERVED_ATTRS and
                    not key.startswith('_') and
                    key not in log_record):
                log_record.setdefault(key, self._safe_json(value))

        # 添加标准字段（这些可能在RESERVED_ATTRS中，但我们想要保留）
        standard_fields = {
            'pathname': record.pathname,
            'filename': record.filename,
            'module': record.module,
            'lineno': record.lineno,
            'funcName': record.funcName,
            'created': record.created,
            'msecs': record.msecs,
            'relativeCreated': record.relativeCreated,
            'thread': record.threadName,
            'threadName': record.threadName,
            'processName': record.processName,
            'process': record.process,
        }

        for field, value in standard_fields.items():
            log_record.setdefault(field, value)

        # 添加追踪信息
        log_record.setdefault('trace_id', getattr(record, 'trace_id', None))
        log_record.setdefault('span_id', getattr(record, 'span_id', None))

        # 调试输出
        self._debug("add_fields - log_record keys: %s", list(log_record.keys()))
        if 'method' in log_record:
            self._debug("add_fields - method found: %s", log_record['method'])
        if 'action' in log_record:
            self._debug("add_fields - action found: %s", log_record['action'])
        if 'operation' in log_record:
            self._debug("add_fields - operation found: %s", log_record['operation'])

    def process_log_record(self, log_record):
        """处理日志记录"""
        # 获取当前时间
        now = self.timezone_formatter.format_time()

        # 添加时间字段（不覆盖已有的）
        log_record.setdefault(
            self.config.json_timestamp_field,
            self.timezone_formatter.format_timestamp(now)
        )

        log_record.setdefault('date', self.timezone_formatter.format_date(now))
        log_record.setdefault('timezone', self.config.timezone.value)
        log_record.setdefault('timestamp_precision', self.config.timestamp_precision.value)

        # 添加其他标准字段
        log_record.setdefault(
            'environment',
            getattr(self.config.__class__, 'environment', 'production')
        )
        log_record.setdefault('service', self.config.name)
        log_record.setdefault('hostname', socket.gethostname())
        log_record.setdefault('pid', os.getpid())

        # 确保 request_id 字段存在
        log_record.setdefault('request_id', '-')

        # 处理异常信息
        if 'exc_info' in log_record and log_record['exc_info']:
            try:
                exc_info = log_record['exc_info']
                if isinstance(exc_info, tuple):
                    exc_type, exc_value, exc_tb = exc_info
                    log_record.setdefault('exception', {
                        'type': exc_type.__name__,
                        'message': str(exc_value),
                        'traceback': traceback.format_exception(
                            exc_type, exc_value, exc_tb
                        )
                    })
            except Exception:
                pass

        # 清理内部字段
        for field in ('exc_info', 'exc_text', 'stack_info', 'args'):
            if field in log_record:
                del log_record[field]

        # 确保所有值都是JSON可序列化的
        for k, v in list(log_record.items()):
            log_record[k] = self._safe_json(v)

        # 调试输出
        self._debug("process_log_record - final keys: %s", list(log_record.keys()))
        if 'method' in log_record:
            self._debug("process_log_record - method preserved: %s", log_record['method'])

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

    def format(self, record):
        """格式化日志记录"""
        # 确保有请求ID
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
        return super().format(record)