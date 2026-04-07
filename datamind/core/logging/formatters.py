# datamind/core/logging/formatters.py

"""日志格式化器

提供日志格式化功能，包括时区转换、JSON格式化和文本格式化。

核心功能：
  - TimezoneFormatter: 时区格式化器，用于文本日志的时区转换
  - CustomJsonFormatter: JSON 格式化器，输出结构化日志
  - CustomTextFormatter: 文本格式化器，输出可读文本日志

特性：
  - 多时区支持：UTC 和 IANA 时区（如 Asia/Shanghai）
  - 多种时间精度：秒/毫秒/微秒/纳秒
  - 自定义日期时间格式
  - JSON 结构化日志
  - 异常信息格式化
  - 敏感信息脱敏
  - UTC 时间戳标准格式（ELK/Loki 兼容）

使用示例：
    from datamind.core.logging.formatters import CustomJsonFormatter, CustomTextFormatter

    # JSON 格式化器
    json_formatter = CustomJsonFormatter(config)
    handler.setFormatter(json_formatter)

    # 文本格式化器
    text_formatter = CustomTextFormatter(config)
    handler.setFormatter(text_formatter)
"""

import os
import sys
import json
import socket
import traceback
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pythonjsonlogger.json import JsonFormatter

from datamind.config.logging_config import (
    LoggingConfig,
    LogField,
)

_logger = logging.getLogger(__name__)

# 格式化器调试开关
_FORMATTER_DEBUG = os.environ.get('DATAMIND_FORMATTER_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """格式化器内部调试输出"""
    if _FORMATTER_DEBUG:
        if args:
            print(f"[Formatter] {msg % args}", file=sys.stderr)
        else:
            print(f"[Formatter] {msg}", file=sys.stderr)


def _mask(value: str, mask_char: str, keep_prefix: int = 3, keep_suffix: int = 3) -> str:
    """脱敏单个值

    参数:
        value: 原始值
        mask_char: 遮蔽字符
        keep_prefix: 保留前缀字符数
        keep_suffix: 保留后缀字符数

    返回:
        脱敏后的值
    """
    if not value:
        return value

    if len(value) <= keep_prefix + keep_suffix:
        return mask_char * len(value)

    return (value[:keep_prefix] +
            mask_char * (len(value) - keep_prefix - keep_suffix) +
            value[-keep_suffix:])


# ==================== 常量定义 ====================

SYSTEM_PROTECTED_FIELDS = {
    LogField.TIMESTAMP, LogField.LEVEL, LogField.LEVEL_NO,
    LogField.MESSAGE, LogField.LOGGER, LogField.SERVICE,
    LogField.ENVIRONMENT, LogField.HOSTNAME, LogField.PID,
    LogField.REQUEST_ID, LogField.TRACE_ID, LogField.SPAN_ID,
    LogField.EXCEPTION_TYPE, LogField.EXCEPTION_MESSAGE,
    LogField.EXCEPTION_STACKTRACE
}

SENSITIVE_KEYWORDS = {
    "password", "token", "secret", "api_key", "api_secret",
    "access_token", "refresh_token", "auth_token",
    "credit_card", "card_number", "cvv", "cvc",
    "id_number", "id_card", "ssn", "social_security",
    "private_key", "pem", "certificate", "pwd", "passwd"
}

PRIMITIVE_TYPES = (str, int, float, bool, type(None))


# ==================== TimezoneFormatter ====================

class TimezoneFormatter:
    """时区格式化器

    负责时区转换和时间格式化，仅用于文本日志。
    JSON 日志的时间戳由 CustomJsonFormatter 直接处理为 UTC 格式。
    """

    def __init__(self, config: LoggingConfig):
        """
        初始化时区格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        _debug("TimezoneFormatter 已创建: timezone=%s", config.timezone)

    def _get_timezone(self):
        """获取时区对象

        返回:
            ZoneInfo 对象，如果时区无效则返回 UTC
        """
        try:
            return ZoneInfo(self.config.timezone)
        except ZoneInfoNotFoundError:
            _debug("时区无效，使用 UTC: %s", self.config.timezone)
            return ZoneInfo("UTC")

    def format_time(self, dt: Optional[datetime] = None) -> datetime:
        """格式化时间（应用时区和偏移）

        参数:
            dt: 要格式化的时间，如果为 None 则使用当前时间

        返回:
            应用时区和偏移后的时间对象
        """
        if dt is None:
            dt = datetime.now()

        tz = self._get_timezone()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone(tz)

        if self.config.time_offset_hours != 0:
            dt = dt + timedelta(hours=self.config.time_offset_hours)

        return dt

    def format_local_time_with_tz(self, dt: datetime) -> str:
        """格式化为带时区的本地时间字符串（用于文本日志）

        参数:
            dt: 要格式化的时间

        返回:
            带时区的本地时间字符串，格式: YYYY-MM-DD HH:MM:SS±HHMM
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        tz = self._get_timezone()
        dt = dt.astimezone(tz)

        return dt.strftime("%Y-%m-%d %H:%M:%S%z")


# ==================== CustomJsonFormatter ====================

class CustomJsonFormatter(JsonFormatter):
    """JSON 格式化器

    输出结构化 JSON 日志，专为 ELK/Loki 等日志系统设计。
    """

    STANDARD_FIELDS = [
        LogField.MODULE, LogField.FILE_NAME, LogField.PATH_NAME,
        LogField.LINE_NO, LogField.FUNC_NAME, LogField.THREAD_NAME,
        LogField.PROCESS_NAME
    ]

    INTERNAL_FIELDS = ['exc_info', 'exc_text', 'stack_info', 'args']

    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def __init__(self, config: LoggingConfig):
        """
        初始化 JSON 格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self._hostname = socket.gethostname()
        self._pid = os.getpid()
        self._sensitive_keywords = set(config.sensitive_fields)
        super().__init__(json_ensure_ascii=False, json_indent=None)
        _debug("CustomJsonFormatter 已创建: hostname=%s, pid=%d", self._hostname, self._pid)

    def _is_sensitive_key(self, key: str) -> bool:
        """检查是否为敏感字段（精确匹配）"""
        return key.lower() in self._sensitive_keywords

    def _mask_fields(self, log_record: Dict[str, Any]) -> None:
        """脱敏敏感字段（精确匹配）"""
        if not self.config.mask_sensitive:
            return

        mask_char = self.config.mask_char

        for key in list(log_record.keys()):
            if self._is_sensitive_key(key):
                value = log_record[key]
                if isinstance(value, str):
                    log_record[key] = _mask(value, mask_char)
                else:
                    log_record[key] = mask_char * 8
                _debug("脱敏敏感字段: %s", key)

    def _safe_json(self, obj: Any) -> Any:
        """安全地将对象转换为 JSON 可序列化格式"""
        if obj is None or isinstance(obj, PRIMITIVE_TYPES):
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

    @staticmethod
    def _add_basic_fields(log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加基本字段"""
        log_record[LogField.LEVEL] = record.levelname
        log_record[LogField.LEVEL_NO] = record.levelno
        log_record[LogField.LOGGER] = record.name
        log_record[LogField.MESSAGE] = record.getMessage()

    def _add_extra_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加 extra 字段（保护系统保留字段）"""
        for key, value in record.__dict__.items():
            if key in self.RESERVED_ATTRS or key.startswith('_'):
                continue
            if key in SYSTEM_PROTECTED_FIELDS:
                continue
            if key in log_record:
                continue
            log_record[key] = self._safe_json(value)

    def _add_standard_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加标准字段（不包含时间字段）"""
        for field in self.STANDARD_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if field not in SYSTEM_PROTECTED_FIELDS:
                    log_record.setdefault(field, value)

    @staticmethod
    def _add_trace_fields(log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加链路追踪字段"""
        trace_id = getattr(record, LogField.TRACE_ID, None)
        span_id = getattr(record, LogField.SPAN_ID, None)
        parent_span_id = getattr(record, LogField.PARENT_SPAN_ID, None)

        if trace_id:
            log_record[LogField.TRACE_ID] = str(trace_id)
        if span_id:
            log_record[LogField.SPAN_ID] = str(span_id)
        if parent_span_id:
            log_record[LogField.PARENT_SPAN_ID] = str(parent_span_id)

    def _add_environment_fields(self, log_record: Dict[str, Any]) -> None:
        """添加环境相关字段"""
        if LogField.ENVIRONMENT not in log_record:
            log_record[LogField.ENVIRONMENT] = getattr(self.config, 'environment', 'production')
        if LogField.SERVICE not in log_record:
            log_record[LogField.SERVICE] = self.config.name
        if LogField.HOSTNAME not in log_record:
            log_record[LogField.HOSTNAME] = self._hostname
        if LogField.PID not in log_record:
            log_record[LogField.PID] = self._pid
        if LogField.REQUEST_ID not in log_record:
            log_record[LogField.REQUEST_ID] = '-'

    @staticmethod
    def _add_exception_info(log_record: Dict[str, Any], record: Optional[logging.LogRecord]) -> None:
        """添加异常信息"""
        if record is None:
            return

        if not hasattr(record, 'exc_info') or not record.exc_info:
            return

        try:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_type:
                log_record[LogField.EXCEPTION_TYPE] = exc_type.__name__
                log_record[LogField.EXCEPTION_MESSAGE] = str(exc_value)
                log_record[LogField.EXCEPTION_STACKTRACE] = ''.join(
                    traceback.format_exception(exc_type, exc_value, exc_tb)
                )
        except Exception as e:
            _logger.warning("处理异常信息时出错: %s", e)

    def _cleanup_internal_fields(self, log_record: Dict[str, Any]) -> None:
        """清理内部字段"""
        for field in self.INTERNAL_FIELDS:
            log_record.pop(field, None)

    def _ensure_json_serializable(self, log_record: Dict[str, Any]) -> None:
        """确保所有值都是 JSON 可序列化的"""
        for k, v in list(log_record.items()):
            if isinstance(v, PRIMITIVE_TYPES):
                continue
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                log_record[k] = self._safe_json(v)

    @staticmethod
    def _format_timestamp_z(record: Optional[logging.LogRecord]) -> str:
        """格式化 UTC Z 时间戳（毫秒精度）

        参数:
            record: 日志记录对象，如果为 None 则返回当前时间戳

        返回:
            UTC Z 格式时间戳，格式: 2024-01-15T10:30:45.123Z
        """
        if record is None:
            dt = datetime.now(timezone.utc)
            ms = int(dt.timestamp() * 1000) % 1000
        else:
            dt = datetime.fromtimestamp(record.created, timezone.utc)
            ms = int(record.created * 1000) % 1000
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.{ms:03d}Z"

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord,
                   message_dict: Dict[str, Any]) -> None:
        """添加字段到日志记录（父类方法重写）"""
        super().add_fields(log_record, record, message_dict)
        log_record["__dm_record__"] = record

        self._add_basic_fields(log_record, record)
        self._add_extra_fields(log_record, record)
        self._add_standard_fields(log_record, record)
        self._add_trace_fields(log_record, record)

    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        """处理日志记录（父类方法重写）"""
        record = log_record.pop("__dm_record__", None)

        log_record[LogField.TIMESTAMP] = self._format_timestamp_z(record)

        if record:
            for field in ["asctime", "created", "msecs", "relativeCreated"]:
                log_record.pop(field, None)

        self._add_exception_info(log_record, record)
        self._add_environment_fields(log_record)
        self._cleanup_internal_fields(log_record)
        self._mask_fields(log_record)
        self._ensure_json_serializable(log_record)

        return log_record


# ==================== CustomTextFormatter ====================

class CustomTextFormatter(logging.Formatter):
    """文本格式化器

    输出可读的文本格式日志，便于人工阅读和开发调试。
    """

    def __init__(self, config: LoggingConfig):
        """
        初始化文本格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        self._sensitive_keywords = set(config.sensitive_fields)
        super().__init__(fmt=config.text_format, datefmt=config.text_datetime_format)
        _debug("CustomTextFormatter 已创建: format=%s", config.text_format if config.text_format else "default")

    def _is_sensitive_key(self, key: str) -> bool:
        """检查是否为敏感字段（精确匹配）"""
        return key.lower() in self._sensitive_keywords

    def _mask_record(self, record: logging.LogRecord) -> None:
        """脱敏记录中的敏感字段"""
        if not self.config.mask_sensitive:
            return

        mask_char = self.config.mask_char

        for attr_name in list(record.__dict__.keys()):
            if attr_name.startswith('_'):
                continue
            if self._is_sensitive_key(attr_name):
                value = getattr(record, attr_name)
                if isinstance(value, str):
                    setattr(record, attr_name, _mask(value, mask_char))
                else:
                    setattr(record, attr_name, mask_char * 8)
                _debug("脱敏敏感属性: %s", attr_name)

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """格式化时间（重写父类方法）

        使用本地时间（带时区），便于人工阅读。
        """
        dt = datetime.fromtimestamp(record.created, timezone.utc)
        return self.timezone_formatter.format_local_time_with_tz(dt)

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录（重写父类方法）"""
        if not hasattr(record, LogField.REQUEST_ID):
            record.request_id = '-'

        self._mask_record(record)

        return super().format(record)


__all__ = [
    "TimezoneFormatter",
    "CustomJsonFormatter",
    "CustomTextFormatter",
]