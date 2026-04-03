# Datamind/datamind/core/logging/formatters.py

"""日志格式化器

提供日志格式化功能：
  - TimezoneFormatter: 时区格式化器，支持时区转换和时间格式定制
  - CustomJsonFormatter: JSON 格式化器，输出结构化日志
  - CustomTextFormatter: 文本格式化器，输出可读文本日志

支持特性：
  - 多时区支持（UTC/本地/CST/EST/PST）
  - 多种时间精度（秒/毫秒/微秒/纳秒）
  - 自定义日期时间格式
  - JSON 结构化日志
  - 异常信息格式化
  - 敏感信息保护（模糊匹配）
  - 敏感字段自动脱敏

注意：
  - 日志采样由 Filter 层实现，不在 Formatter 层处理
  - JSON 日志时间统一使用 UTC Z 格式
  - 文本日志使用本地时间（带时区）
"""

import os
import json
import pytz
import socket
import traceback
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Union, Dict, Any, List, Tuple
from pythonjsonlogger import json as jsonlogger

from datamind.config import (
    LoggingConfig, LogFormat, TimeZone, TimestampPrecision,
    LogField
)
from datamind.core.logging.debug import debug_print

# ==================== 常量定义 ====================

# 系统保留字段（不允许被 extra 覆盖）
SYSTEM_PROTECTED_FIELDS = {
    LogField.TIMESTAMP, LogField.LEVEL, LogField.LEVEL_NO,
    LogField.MESSAGE, LogField.LOGGER, LogField.SERVICE,
    LogField.ENVIRONMENT, LogField.HOSTNAME, LogField.PID,
    LogField.REQUEST_ID, LogField.TRACE_ID, LogField.SPAN_ID,
    LogField.EXCEPTION_TYPE, LogField.EXCEPTION_MESSAGE,
    LogField.EXCEPTION_STACKTRACE
}

# 敏感字段关键词（模糊匹配）
SENSITIVE_KEYWORDS = {
    "password", "token", "secret", "api_key", "api_secret",
    "access_token", "refresh_token", "auth_token",
    "credit_card", "card_number", "cvv", "cvc",
    "id_number", "id_card", "ssn", "social_security",
    "private_key", "pem", "certificate", "pwd", "passwd"
}

# 可直接返回的基本类型（无需递归处理）
PRIMITIVE_TYPES = (str, int, float, bool, type(None))


# ==================== TimezoneFormatter ====================

class TimezoneFormatter:
    """时区格式化器

    负责时区转换和时间格式化，仅用于文本日志和本地时间展示。
    JSON 日志的 UTC 时间直接由 CustomJsonFormatter 处理。
    """

    # 时区映射表
    TIMEZONE_MAP = {
        TimeZone.UTC: timezone.utc,
        TimeZone.LOCAL: None,
        TimeZone.CST: pytz.timezone('Asia/Shanghai'),
        TimeZone.EST: pytz.timezone('US/Eastern'),
        TimeZone.PST: pytz.timezone('US/Pacific')
    }

    # Java 到 Python 日期格式映射
    DATE_FORMAT_MAP = {
        "yyyy": "%Y", "yy": "%y", "MM": "%m", "M": "%m",
        "dd": "%d", "d": "%d", "HH": "%H", "H": "%H",
        "hh": "%I", "h": "%I", "mm": "%M", "m": "%M",
        "ss": "%S", "s": "%S", "SSS": "%f",
        "ZZZ": "%z", "Z": "%z", "XXX": "%z",
        "a": "%p", "EEEE": "%A", "EEE": "%a",
        "MMMM": "%B", "MMM": "%b", "ww": "%W", "w": "%W",
    }

    def __init__(self, config: LoggingConfig):
        """
        初始化时区格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone = self._get_timezone()
        self._debug("初始化 TimezoneFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _get_timezone(self) -> Optional[timezone]:
        """
        获取时区对象

        返回:
            时区对象，如果使用本地时区则返回 None
        """
        tz = self.TIMEZONE_MAP.get(self.config.timezone, timezone.utc)

        # 如果是 LOCAL，自动检测系统时区
        if self.config.timezone == TimeZone.LOCAL and tz is None:
            try:
                import tzlocal
                tz = tzlocal.get_localzone()
                self._debug("自动检测系统时区: %s", tz)
            except ImportError:
                # 如果没有安装 tzlocal，使用系统本地时区的替代方案
                import time
                local_offset = -time.timezone if not time.daylight else -time.altzone
                tz = timezone(timedelta(seconds=local_offset))
                self._debug("使用系统偏移量时区: UTC%+03d:00", local_offset // 3600)

        self._debug("获取时区对象: %s -> %s", self.config.timezone.value, tz)
        return tz

    def _convert_java_to_python_format(self, java_format: str) -> str:
        """
        将 Java 日期格式转换为 Python 格式

        参数:
            java_format: Java 日期格式字符串

        返回:
            Python 日期格式字符串
        """
        python_format = java_format
        patterns = sorted(self.DATE_FORMAT_MAP.items(), key=lambda x: len(x[0]), reverse=True)
        for java_pattern, python_pattern in patterns:
            python_format = python_format.replace(java_pattern, python_pattern)
        return python_format

    def _get_python_date_format(self) -> str:
        """
        获取 Python 日期格式

        返回:
            Python 日期格式字符串
        """
        if self.config.format == LogFormat.JSON:
            return self._convert_java_to_python_format(self.config.json_datetime_format)
        return self.config.text_datetime_format

    def format_time(self, dt: datetime) -> datetime:
        """
        格式化时间（应用时区和精度）

        参数:
            dt: 要格式化的时间（必须传入，禁止使用当前时间）

        返回:
            应用时区和偏移后的时间对象

        异常:
            ValueError: 如果 dt 为 None
        """
        if dt is None:
            raise ValueError("format_time() 必须传入 dt，禁止使用当前时间")

        if dt.tzinfo is None and self.timezone is not None:
            dt = dt.replace(tzinfo=timezone.utc)

        if self.timezone:
            dt = dt.astimezone(self.timezone)

        if hasattr(self.config, 'time_offset_hours') and self.config.time_offset_hours != 0:
            dt = dt + timedelta(hours=self.config.time_offset_hours)

        return dt

    def format_local_time_with_tz(self, dt: datetime) -> str:
        """
        格式化为带时区的本地时间字符串（用于文本日志）

        参数:
            dt: 要格式化的时间

        返回:
            带时区的本地时间字符串，格式: YYYY-MM-DD HH:MM:SS±HHMM
        """
        # 如果 dt 没有时区信息，先标记为 UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # 应用配置的时区
        if self.timezone:
            dt = dt.astimezone(self.timezone)

        return dt.strftime("%Y-%m-%d %H:%M:%S%z")


# ==================== CustomJsonFormatter ====================

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON格式化器

    输出结构化 JSON 日志，支持：
      - UTC Z 格式时间戳（ELK/Loki 标准）
      - 敏感字段自动脱敏
      - 系统保留字段保护
      - 异常信息结构化
    """

    # 标准字段列表（不包含时间字段）
    STANDARD_FIELDS = [
        LogField.MODULE, LogField.FILE_NAME, LogField.PATH_NAME,
        LogField.LINE_NO, LogField.FUNC_NAME, LogField.THREAD_NAME,
        LogField.PROCESS_NAME
    ]

    # 需要清理的内部字段
    INTERNAL_FIELDS = ['exc_info', 'exc_text', 'stack_info', 'args']

    # LogRecord 保留属性集合
    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def __init__(self, config: LoggingConfig):
        """
        初始化JSON格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self._hostname = socket.gethostname()
        self._sensitive_keywords = SENSITIVE_KEYWORDS
        super().__init__(json_ensure_ascii=False, json_indent=None)
        self._debug("初始化 CustomJsonFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _is_sensitive_key(self, key: str) -> bool:
        """
        检查是否为敏感字段（模糊匹配）

        参数:
            key: 字段名

        返回:
            True 表示敏感字段，False 表示不是
        """
        key_lower = key.lower()
        return any(kw in key_lower for kw in self._sensitive_keywords)

    def _mask_sensitive(self, log_record: Dict[str, Any]) -> None:
        """
        脱敏敏感字段（模糊匹配）

        参数:
            log_record: 日志记录字典
        """
        if not self.config.mask_sensitive:
            return

        for key in list(log_record.keys()):
            if self._is_sensitive_key(key):
                log_record[key] = "***"

    def _safe_json(self, obj: Any) -> Any:
        """
        安全地将对象转换为JSON可序列化格式

        参数:
            obj: 要转换的对象

        返回:
            JSON可序列化的对象
        """
        # 基本类型直接返回
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

        # 其他类型尝试序列化
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            self._debug("无法序列化的对象: %s，转换为字符串", type(obj))
            return str(obj)

    def _add_basic_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """
        添加基本字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        log_record[LogField.LEVEL] = record.levelname
        log_record[LogField.LEVEL_NO] = record.levelno
        log_record[LogField.LOGGER] = record.name
        log_record[LogField.MESSAGE] = record.getMessage()

    def _add_extra_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """
        添加 extra 字段（保护系统保留字段）

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        extra_count = 0
        for key, value in record.__dict__.items():
            # 跳过系统保留属性
            if key in self.RESERVED_ATTRS or key.startswith('_'):
                continue
            # 保护系统保留字段
            if key in SYSTEM_PROTECTED_FIELDS:
                continue
            # 避免覆盖已有字段
            if key in log_record:
                continue
            log_record[key] = self._safe_json(value)
            extra_count += 1
        if extra_count > 0:
            self._debug("添加 %d 个extra字段", extra_count)

    def _add_standard_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """
        添加标准字段（不包含时间字段）

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        for field in self.STANDARD_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if field not in SYSTEM_PROTECTED_FIELDS:
                    log_record.setdefault(field, value)

    def _add_trace_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """
        添加链路追踪字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
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
        """
        添加环境相关字段

        参数:
            log_record: 日志记录字典
        """
        if LogField.ENVIRONMENT not in log_record:
            log_record[LogField.ENVIRONMENT] = getattr(self.config, 'environment', 'production')
        if LogField.SERVICE not in log_record:
            log_record[LogField.SERVICE] = self.config.name
        if LogField.HOSTNAME not in log_record:
            log_record[LogField.HOSTNAME] = self._hostname
        if LogField.PID not in log_record:
            log_record[LogField.PID] = os.getpid()
        if LogField.REQUEST_ID not in log_record:
            log_record[LogField.REQUEST_ID] = '-'

    def _add_exception_info(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """
        添加异常信息

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
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
            self._debug("处理异常信息时出错: %s", e)

    def _cleanup_internal_fields(self, log_record: Dict[str, Any]) -> None:
        """
        清理内部字段

        参数:
            log_record: 日志记录字典
        """
        for field in self.INTERNAL_FIELDS:
            log_record.pop(field, None)

    def _ensure_json_serializable(self, log_record: Dict[str, Any]) -> None:
        """
        确保所有值都是JSON可序列化的

        对非基本类型的值进行递归处理，确保整个日志记录可以被 json.dumps() 序列化。

        参数:
            log_record: 日志记录字典
        """
        for k, v in list(log_record.items()):
            if isinstance(v, PRIMITIVE_TYPES):
                continue
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                log_record[k] = self._safe_json(v)

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord,
                   message_dict: Dict[str, Any]) -> None:
        """
        添加字段到日志记录（父类方法重写）

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
            message_dict: 消息字典
        """
        super().add_fields(log_record, record, message_dict)
        # 保存 record 供 process_log_record 使用
        log_record["__dm_record__"] = record

        self._add_basic_fields(log_record, record)
        self._add_extra_fields(log_record, record)
        self._add_standard_fields(log_record, record)
        self._add_trace_fields(log_record, record)

    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理日志记录（父类方法重写）

        这是日志格式化的核心方法，负责：
          - 从 record.created 生成 UTC Z 格式时间戳
          - 删除父类添加的污染字段
          - 添加异常信息
          - 添加环境字段
          - 清理内部字段
          - 脱敏敏感信息
          - 确保 JSON 可序列化

        参数:
            log_record: 日志记录字典

        返回:
            处理后的日志记录字典
        """
        record = log_record.pop("__dm_record__", None)

        if record:
            # JSON 日志：使用 UTC Z 格式（ELK/Loki 标准）
            dt = datetime.fromtimestamp(record.created, timezone.utc)
            log_record[LogField.TIMESTAMP] = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            # 删除父类添加的污染字段
            for field in ["asctime", "created", "msecs", "relativeCreated"]:
                log_record.pop(field, None)

            self._add_exception_info(log_record, record)

        self._add_environment_fields(log_record)
        self._cleanup_internal_fields(log_record)
        self._mask_sensitive(log_record)
        self._ensure_json_serializable(log_record)

        return log_record


# ==================== CustomTextFormatter ====================

class CustomTextFormatter(logging.Formatter):
    """自定义文本格式化器

    输出可读的文本格式日志，使用本地时间（带时区），便于人工阅读。
    """

    def __init__(self, config: LoggingConfig):
        """
        初始化文本格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        self._sensitive_keywords = SENSITIVE_KEYWORDS
        super().__init__(fmt=config.text_format, datefmt=config.text_datetime_format)
        self._debug("初始化 CustomTextFormatter，格式: %s", config.text_format)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _is_sensitive_key(self, key: str) -> bool:
        """
        检查是否为敏感字段（模糊匹配）

        参数:
            key: 字段名

        返回:
            True 表示敏感字段，False 表示不是
        """
        key_lower = key.lower()
        return any(kw in key_lower for kw in self._sensitive_keywords)

    def _mask_sensitive(self, record: logging.LogRecord) -> None:
        """
        脱敏敏感字段

        只处理 record.__dict__ 中的属性，避免遍历 dir(record) 带来的性能问题。

        参数:
            record: 日志记录对象
        """
        if not self.config.mask_sensitive:
            return

        for attr_name in list(record.__dict__.keys()):
            if attr_name.startswith('_'):
                continue
            if self._is_sensitive_key(attr_name):
                record.__dict__[attr_name] = "***"

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """
        格式化时间（重写父类方法）

        使用本地时间（带时区），便于人工阅读。

        参数:
            record: 日志记录对象
            datefmt: 日期格式（未使用）

        返回:
            格式化的时间字符串
        """
        # record.created 是 UTC 时间戳，先转换为 UTC datetime
        dt = datetime.fromtimestamp(record.created, timezone.utc)
        return self.timezone_formatter.format_local_time_with_tz(dt)

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录（重写父类方法）

        参数:
            record: 日志记录对象

        返回:
            格式化的日志字符串
        """
        # 确保有请求ID
        if not hasattr(record, LogField.REQUEST_ID):
            record.request_id = '-'

        # 敏感信息脱敏
        self._mask_sensitive(record)

        return super().format(record)