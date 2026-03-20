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
  - 敏感信息保护
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

from datamind.config import LoggingConfig, LogFormat, TimeZone, TimestampPrecision
from datamind.core.logging.debug import debug_print


class TimezoneFormatter:
    """时区格式化器"""

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
        "yyyy": "%Y",
        "yy": "%y",
        "MM": "%m",
        "M": "%m",
        "dd": "%d",
        "d": "%d",
        "HH": "%H",
        "H": "%H",
        "hh": "%I",
        "h": "%I",
        "mm": "%M",
        "m": "%M",
        "ss": "%S",
        "s": "%S",
        "SSS": "%f",  # 毫秒
        "ZZZ": "%z",
        "Z": "%z",
        "XXX": "%z",
        "a": "%p",
        "EEEE": "%A",
        "EEE": "%a",
        "MMMM": "%B",
        "MMM": "%b",
        "ww": "%W",  # 周数
        "w": "%W",
    }

    def __init__(self, config: LoggingConfig):
        """初始化时区格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone = self._get_timezone()
        self._debug("初始化 TimezoneFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _get_timezone(self) -> Optional[timezone]:
        """获取时区对象

        返回:
            时区对象，如果使用本地时区则返回 None
        """
        tz = self.TIMEZONE_MAP.get(self.config.timezone, timezone.utc)
        self._debug("获取时区对象: %s -> %s", self.config.timezone.value, tz)
        return tz

    def _convert_java_to_python_format(self, java_format: str) -> str:
        """将 Java 日期格式转换为 Python 格式

        参数:
            java_format: Java 日期格式字符串

        返回:
            Python 日期格式字符串
        """
        python_format = java_format

        # 按长度排序，优先匹配更长的模式
        patterns = sorted(self.DATE_FORMAT_MAP.items(), key=lambda x: len(x[0]), reverse=True)

        for java_pattern, python_pattern in patterns:
            python_format = python_format.replace(java_pattern, python_pattern)

        self._debug("转换日期格式: %s -> %s", java_format, python_format)
        return python_format

    def _get_python_date_format(self) -> str:
        """获取 Python 日期格式

        返回:
            Python 日期格式字符串
        """
        if self.config.format == LogFormat.JSON:
            return self._convert_java_to_python_format(self.config.json_datetime_format)
        else:
            return self.config.text_datetime_format

    def format_time(self, dt: Optional[datetime] = None) -> datetime:
        """格式化时间（应用时区和精度）

        参数:
            dt: 要格式化的时间，如果为 None 则使用当前时间

        返回:
            应用时区和偏移后的时间对象
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
            self._debug("使用当前UTC时间: %s", dt)

        original_dt = dt

        # 确保时间有时区信息
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            self._debug("添加UTC时区信息")

        # 应用时区转换
        if self.timezone:
            dt = dt.astimezone(self.timezone)
            self._debug("应用时区转换: %s -> %s", original_dt, dt)

        # 应用时间偏移
        if hasattr(self.config, 'time_offset_hours') and self.config.time_offset_hours != 0:
            dt = dt + timedelta(hours=self.config.time_offset_hours)
            self._debug("应用时间偏移 %d 小时: %s", self.config.time_offset_hours, dt)

        return dt

    def _format_timestamp_as_epoch(self, dt: datetime) -> Union[int, float]:
        """将时间格式化为时间戳

        参数:
            dt: 时间对象

        返回:
            时间戳（秒、毫秒、微秒或纳秒）
        """
        timestamp = dt.timestamp()
        self._debug("基础时间戳: %f", timestamp)

        unit = self.config.json_epoch_unit
        if unit == 'milliseconds':
            result = timestamp * 1000
            self._debug("转换为毫秒: %f", result)
        elif unit == 'microseconds':
            result = timestamp * 1_000_000
            self._debug("转换为微秒: %f", result)
        elif unit == 'nanoseconds':
            result = timestamp * 1_000_000_000
            self._debug("转换为纳秒: %f", result)
        else:
            result = timestamp
            self._debug("使用秒为单位: %f", result)

        # 根据精度返回整数或浮点数
        if unit == 'seconds' and self.config.timestamp_precision == TimestampPrecision.SECONDS:
            return int(result)
        return result

    def _format_timestamp_as_string(self, dt: datetime) -> str:
        """将时间格式化为字符串

        参数:
            dt: 时间对象

        返回:
            格式化的时间字符串
        """
        fmt = self._get_python_date_format()
        formatted = dt.strftime(fmt)

        # 处理微秒精度（如果需要截断到毫秒）
        if self.config.timestamp_precision == TimestampPrecision.MILLISECONDS and '.' in formatted:
            parts = formatted.split('.')
            if len(parts) == 2:
                # 截断到毫秒（3位）
                formatted = f"{parts[0]}.{parts[1][:3]}"
            elif len(parts) == 3:
                # 处理带时区的情况，如 2024-01-01 12:00:00.123456+0800
                time_part, ms_part, tz_part = parts[0], parts[1][:3], parts[2]
                formatted = f"{time_part}.{ms_part}{tz_part}"

        self._debug("格式化时间字符串: %s, 格式: %s", formatted, fmt)
        return formatted

    def format_timestamp(self, dt: Optional[datetime] = None) -> Union[str, int, float]:
        """格式化时间戳

        参数:
            dt: 要格式化的时间，如果为 None 则使用当前时间

        返回:
            格式化的时间戳（字符串或数字）
        """
        dt = self.format_time(dt)

        if self.config.json_use_epoch:
            return self._format_timestamp_as_epoch(dt)
        else:
            return self._format_timestamp_as_string(dt)

    def format_date(self, dt: Optional[datetime] = None) -> str:
        """格式化日期

        参数:
            dt: 要格式化的时间，如果为 None 则使用当前时间

        返回:
            格式化的日期字符串
        """
        dt = self.format_time(dt)

        if self.config.format == LogFormat.JSON:
            if hasattr(self.config, 'json_date_format'):
                fmt = self._convert_java_to_python_format(self.config.json_date_format)
                self._debug("转换JSON日期格式: %s -> %s", self.config.json_date_format, fmt)
            else:
                fmt = "%Y-%m-%d"
                self._debug("使用默认JSON日期格式: %s", fmt)
        else:
            fmt = self.config.text_date_format
            self._debug("使用文本日期格式: %s", fmt)

        result = dt.strftime(fmt)
        self._debug("格式化日期结果: %s", result)
        return result


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON格式化器"""

    # 标准字段列表
    STANDARD_FIELDS = [
        'pathname', 'filename', 'module', 'lineno', 'funcName',
        'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
        'processName', 'process'
    ]

    # 需要清理的内部字段
    INTERNAL_FIELDS = ['exc_info', 'exc_text', 'stack_info', 'args']

    # 获取LogRecord的所有保留属性
    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def __init__(self, config: LoggingConfig):
        """初始化JSON格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            json_ensure_ascii=False,
            json_indent=None
        )
        self._debug("初始化 CustomJsonFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _safe_json(self, obj: Any) -> Any:
        """安全地将对象转换为JSON可序列化格式

        参数:
            obj: 要转换的对象

        返回:
            JSON可序列化的对象
        """
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, (datetime, date)):
            iso = obj.isoformat()
            self._debug("转换日期时间: %s -> %s", obj, iso)
            return iso

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
            self._debug("无法序列化的对象: %s，转换为字符串", type(obj))
            return str(obj)

    def _add_basic_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加基本字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        log_record.setdefault('level', record.levelname)
        log_record.setdefault('logger', record.name)
        log_record.setdefault('message', record.getMessage())

        # 调试预览
        msg_preview = record.getMessage()
        if len(msg_preview) > 50:
            msg_preview = msg_preview[:50] + "..."
        self._debug("添加基本字段: level=%s, logger=%s, message=%s",
                    record.levelname, record.name, msg_preview)

    def _add_extra_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加 extra 字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        extra_count = 0

        for key, value in record.__dict__.items():
            # 如果不是保留属性、不是私有属性、且还未在log_record中
            if (key not in self.RESERVED_ATTRS and
                    not key.startswith('_') and
                    key not in log_record):
                log_record.setdefault(key, self._safe_json(value))
                extra_count += 1

                # 调试输出
                value_preview = str(value)
                if len(value_preview) > 50:
                    value_preview = value_preview[:50] + "..."
                self._debug("添加extra字段: %s = %s", key, value_preview)

        if extra_count > 0:
            self._debug("共添加 %d 个extra字段", extra_count)

    def _add_standard_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加标准字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        for field in self.STANDARD_FIELDS:
            if hasattr(record, field):
                log_record.setdefault(field, getattr(record, field))

    def _add_trace_fields(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加追踪字段

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        trace_id = getattr(record, 'trace_id', None)
        span_id = getattr(record, 'span_id', None)
        log_record.setdefault('trace_id', trace_id)
        log_record.setdefault('span_id', span_id)

        if trace_id or span_id:
            self._debug("添加追踪信息: trace_id=%s, span_id=%s", trace_id, span_id)

    def _add_timestamp_fields(self, log_record: Dict[str, Any]) -> None:
        """添加时间相关字段

        参数:
            log_record: 日志记录字典
        """
        now = self.timezone_formatter.format_time()
        self._debug("当前时间: %s", now)

        # 添加时间戳字段
        timestamp_field = self.config.json_timestamp_field
        if timestamp_field not in log_record:
            timestamp_value = self.timezone_formatter.format_timestamp(now)
            log_record[timestamp_field] = timestamp_value
            self._debug("添加时间戳字段: %s = %s", timestamp_field, timestamp_value)

        # 添加日期字段
        if 'date' not in log_record:
            log_record['date'] = self.timezone_formatter.format_date(now)
            self._debug("添加日期字段: %s", log_record['date'])

        # 添加时区字段
        if 'timezone' not in log_record:
            log_record['timezone'] = self.config.timezone.value
            self._debug("添加时区字段: %s", self.config.timezone.value)

        # 添加精度字段
        if 'timestamp_precision' not in log_record:
            log_record['timestamp_precision'] = self.config.timestamp_precision.value
            self._debug("添加精度字段: %s", self.config.timestamp_precision.value)

    def _add_environment_fields(self, log_record: Dict[str, Any]) -> None:
        """添加环境相关字段

        参数:
            log_record: 日志记录字典
        """
        # 环境
        if 'environment' not in log_record:
            env = getattr(self.config, 'environment', 'production')
            log_record['environment'] = env
            self._debug("添加环境字段: %s", env)

        # 服务名称
        if 'service' not in log_record:
            log_record['service'] = self.config.name
            self._debug("添加服务字段: %s", self.config.name)

        # 主机名
        if 'hostname' not in log_record:
            hostname = socket.gethostname()
            log_record['hostname'] = hostname
            self._debug("添加主机名字段: %s", hostname)

        # 进程ID
        if 'pid' not in log_record:
            pid = os.getpid()
            log_record['pid'] = pid
            self._debug("添加进程ID字段: %d", pid)

        # 请求ID
        if 'request_id' not in log_record:
            log_record['request_id'] = '-'
            self._debug("添加默认request_id: -")

    def _add_exception_info(self, log_record: Dict[str, Any], record: logging.LogRecord) -> None:
        """添加异常信息

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
        """
        if 'exc_info' not in log_record or not log_record['exc_info']:
            return

        self._debug("处理异常信息")
        try:
            exc_info = log_record['exc_info']
            if isinstance(exc_info, tuple):
                exc_type, exc_value, exc_tb = exc_info
                exception_info = {
                    'type': exc_type.__name__,
                    'message': str(exc_value),
                    'traceback': traceback.format_exception(
                        exc_type, exc_value, exc_tb
                    )
                }
                log_record.setdefault('exception', exception_info)
                self._debug("异常信息: %s: %s", exc_type.__name__, str(exc_value))
        except Exception as e:
            self._debug("处理异常信息时出错: %s", e)

    def _cleanup_internal_fields(self, log_record: Dict[str, Any]) -> None:
        """清理内部字段

        参数:
            log_record: 日志记录字典
        """
        cleaned = 0
        for field in self.INTERNAL_FIELDS:
            if field in log_record:
                del log_record[field]
                cleaned += 1

        if cleaned > 0:
            self._debug("清理了 %d 个内部字段", cleaned)

    def _ensure_json_serializable(self, log_record: Dict[str, Any]) -> None:
        """确保所有值都是JSON可序列化的

        参数:
            log_record: 日志记录字典
        """
        serialized_count = 0
        for k, v in list(log_record.items()):
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                log_record[k] = self._safe_json(v)
                serialized_count += 1

        if serialized_count > 0:
            self._debug("对 %d 个字段进行了安全序列化", serialized_count)

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord,
                   message_dict: Dict[str, Any]) -> None:
        """添加字段到日志记录

        参数:
            log_record: 日志记录字典
            record: 原始日志记录
            message_dict: 消息字典
        """
        # 调用父类方法
        super().add_fields(log_record, record, message_dict)
        self._debug("父类添加字段后: %s", list(log_record.keys()))

        # 添加各类字段
        self._add_basic_fields(log_record, record)
        self._add_extra_fields(log_record, record)
        self._add_standard_fields(log_record, record)
        self._add_trace_fields(log_record, record)

        # 调试输出
        self._debug("日志记录字段列表: %s", list(log_record.keys()))

    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        """处理日志记录

        参数:
            log_record: 日志记录字典

        返回:
            处理后的日志记录字典
        """
        self._debug("开始处理日志记录，当前字段: %d个", len(log_record))

        # 添加时间相关字段
        self._add_timestamp_fields(log_record)

        # 添加环境相关字段
        self._add_environment_fields(log_record)

        # 处理异常信息
        self._add_exception_info(log_record, logging.LogRecord("", 0, "", 0, "", (), None))

        # 清理内部字段
        self._cleanup_internal_fields(log_record)

        # 确保JSON可序列化
        self._ensure_json_serializable(log_record)

        # 调试输出
        all_keys = list(log_record.keys())
        keys_preview = all_keys[:10]
        if len(all_keys) > 10:
            keys_preview.append(f"... 共{len(all_keys)}个字段")
        self._debug("最终字段预览: %s", keys_preview)

        return log_record


class CustomTextFormatter(logging.Formatter):
    """自定义文本格式化器"""

    def __init__(self, config: LoggingConfig):
        """初始化文本格式化器

        参数:
            config: 日志配置对象
        """
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            fmt=config.text_format,
            datefmt=config.text_datetime_format
        )
        self._debug("初始化 CustomTextFormatter，格式: %s", config.text_format)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """格式化时间

        参数:
            record: 日志记录对象
            datefmt: 日期格式（未使用）

        返回:
            格式化的时间字符串
        """
        created_time = datetime.fromtimestamp(record.created)
        self._debug("格式化时间，原始时间: %s", created_time)

        # 使用时区格式化器获取格式化的时间戳
        formatted_time = self.timezone_formatter.format_timestamp(created_time)
        self._debug("格式化后的时间: %s", formatted_time)

        if isinstance(formatted_time, (int, float)):
            # 如果是时间戳，转换为字符串
            if self.config.timestamp_precision == TimestampPrecision.SECONDS:
                result = str(int(formatted_time))
                self._debug("转换为秒字符串: %s", result)
            elif self.config.timestamp_precision == TimestampPrecision.MILLISECONDS:
                result = f"{formatted_time:.0f}"
                self._debug("转换为毫秒字符串: %s", result)
            else:
                result = str(formatted_time)
                self._debug("转换为字符串: %s", result)
            return result

        return formatted_time

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录

        参数:
            record: 日志记录对象

        返回:
            格式化的日志字符串
        """
        # 确保有请求ID
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
            self._debug("为日志记录添加默认request_id")
        else:
            self._debug("日志记录已有request_id: %s", record.request_id)

        # 调试预览
        msg_preview = record.getMessage()
        if len(msg_preview) > 50:
            msg_preview = msg_preview[:50] + "..."
        self._debug("开始格式化文本日志: %s", msg_preview)

        result = super().format(record)
        self._debug("文本日志格式化完成")
        return result