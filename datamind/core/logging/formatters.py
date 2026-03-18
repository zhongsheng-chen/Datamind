# Datamind/datamind/core/logging/formatters.py

import os
import json
import pytz
import socket
import traceback
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Union
from pythonjsonlogger import jsonlogger
from datamind.config import LoggingConfig, LogFormat, TimeZone, TimestampPrecision
from datamind.core.logging.debug import debug_print


class TimezoneFormatter:
    """时区格式化器"""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone = self._get_timezone()
        self._debug("初始化 TimezoneFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _get_timezone(self):
        """获取时区对象"""
        tz_map = {
            TimeZone.UTC: timezone.utc,
            TimeZone.LOCAL: None,  # 使用本地时间
            TimeZone.CST: pytz.timezone('Asia/Shanghai'),
            TimeZone.EST: pytz.timezone('US/Eastern'),
            TimeZone.PST: pytz.timezone('US/Pacific')
        }
        tz = tz_map.get(self.config.timezone, timezone.utc)
        self._debug("获取时区对象: %s -> %s", self.config.timezone.value, tz)
        return tz

    def _convert_java_to_python_format(self, java_format: str) -> str:
        """将 Java 日期格式转换为 Python 格式"""
        mapping = {
            "yyyy": "%Y",
            "yy": "%y",
            "MM": "%m",
            "dd": "%d",
            "HH": "%H",
            "hh": "%I",   # 12小时制
            "mm": "%M",
            "ss": "%S",
            "SSS": "%f",  # 毫秒，Python 使用微秒
            "ZZZ": "%z",
            "Z": "%z",
            "XXX": "%z",
            "a": "%p",    # AM/PM
            "EEEE": "%A", # 星期全称
            "EEE": "%a",  # 星期缩写
            "MMMM": "%B", # 月份全称
            "MMM": "%b",  # 月份缩写
        }

        python_format = java_format
        for java_pattern, python_pattern in mapping.items():
            python_format = python_format.replace(java_pattern, python_pattern)

        # 处理毫秒（Python 的 %f 是微秒，需要截断）
        if "%f" in python_format:
            # 保留前3位作为毫秒
            python_format = python_format.replace("%f", "%f")  # 保持原样，使用时截断

        self._debug("转换日期格式: %s -> %s", java_format, python_format)
        return python_format

    def _get_python_date_format(self) -> str:
        """获取 Python 日期格式"""
        if self.config.format == LogFormat.JSON:
            # JSON 格式使用配置的 json_datetime_format
            return self._convert_java_to_python_format(self.config.json_datetime_format)
        else:
            # 文本格式直接使用 text_datetime_format
            return self.config.text_datetime_format

    def format_time(self, dt: Optional[datetime] = None) -> datetime:
        """格式化时间（应用时区和精度）"""
        if dt is None:
            dt = datetime.now(timezone.utc)
            self._debug("使用当前UTC时间: %s", dt)

        original_dt = dt

        # 应用时区
        if self.timezone:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
                self._debug("添加UTC时区信息")
            dt = dt.astimezone(self.timezone)
            self._debug("应用时区转换: %s -> %s", original_dt, dt)

        # 应用时间偏移
        if hasattr(self.config, 'time_offset_hours') and self.config.time_offset_hours != 0:
            dt = dt + timedelta(hours=self.config.time_offset_hours)
            self._debug("应用时间偏移 %d 小时: %s", self.config.time_offset_hours, dt)

        return dt

    def format_timestamp(self, dt: Optional[datetime] = None) -> Union[str, float]:
        """格式化时间戳"""
        dt = self.format_time(dt)
        self._debug("格式化时间戳，输入时间: %s", dt)

        if self.config.json_use_epoch:
            # 返回时间戳
            timestamp = dt.timestamp()
            self._debug("基础时间戳: %f", timestamp)

            if self.config.json_epoch_unit == 'milliseconds':
                result = timestamp * 1000
                self._debug("转换为毫秒: %f", result)
            elif self.config.json_epoch_unit == 'microseconds':
                result = timestamp * 1_000_000
                self._debug("转换为微秒: %f", result)
            elif self.config.json_epoch_unit == 'nanoseconds':
                result = timestamp * 1_000_000_000
                self._debug("转换为纳秒: %f", result)
            else:
                result = timestamp
                self._debug("使用秒为单位: %f", result)
            return result
        else:
            # 返回格式化的时间字符串
            fmt = self._get_python_date_format()
            formatted = dt.strftime(fmt)

            # 处理微秒精度（如果需要截断到毫秒）
            if self.config.timestamp_precision == TimestampPrecision.MILLISECONDS and '.' in formatted:
                # 截断到毫秒（3位）
                parts = formatted.split('.')
                if len(parts) == 2:
                    formatted = f"{parts[0]}.{parts[1][:3]}"

            self._debug("格式化时间字符串: %s, 格式: %s", formatted, fmt)
            return formatted

    def format_date(self, dt: Optional[datetime] = None) -> str:
        """格式化日期"""
        dt = self.format_time(dt)
        self._debug("格式化日期，输入时间: %s", dt)

        if self.config.format == LogFormat.JSON:
            # 检查是否有 json_date_format 属性
            if hasattr(self.config, 'json_date_format'):
                fmt = self._convert_java_to_python_format(self.config.json_date_format)
                self._debug("转换JSON日期格式: %s -> %s", self.config.json_date_format, fmt)
            else:
                # 如果没有，使用默认格式
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

    # 获取LogRecord的所有保留属性
    RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.timezone_formatter = TimezoneFormatter(config)
        super().__init__(
            json_ensure_ascii=False,
            json_indent=None
        )
        self._debug("初始化 CustomJsonFormatter，时区: %s", config.timezone.value)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _safe_json(self, obj):
        """安全地将对象转换为JSON可序列化格式"""
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

    def add_fields(self, log_record, record, message_dict):
        # 先调用父类方法
        super().add_fields(log_record, record, message_dict)
        self._debug("父类添加字段后: %s", list(log_record.keys()))

        # 添加基本字段
        log_record.setdefault('level', record.levelname)
        log_record.setdefault('logger', record.name)
        log_record.setdefault('message', record.getMessage())

        # 安全地截断长消息用于调试
        msg_preview = record.getMessage()
        if len(msg_preview) > 50:
            msg_preview = msg_preview[:50] + "..."
        self._debug("添加基本字段: level=%s, logger=%s, message=%s",
                    record.levelname, record.name, msg_preview)

        # 添加所有 extra 字段
        extra_count = 0
        for key, value in record.__dict__.items():
            # 如果不是保留属性、不是私有属性、且还未在log_record中
            if (key not in self.RESERVED_ATTRS and
                    not key.startswith('_') and
                    key not in log_record):
                log_record.setdefault(key, self._safe_json(value))
                extra_count += 1
                # 避免在调试输出中打印过大的值
                value_preview = str(value)
                if len(value_preview) > 50:
                    value_preview = value_preview[:50] + "..."
                self._debug("添加extra字段: %s = %s", key, value_preview)

        if extra_count > 0:
            self._debug("共添加 %d 个extra字段", extra_count)

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
            'thread': record.thread,
            'threadName': record.threadName,
            'processName': record.processName,
            'process': record.process,
        }

        for field, value in standard_fields.items():
            log_record.setdefault(field, value)

        # 添加追踪信息
        trace_id = getattr(record, 'trace_id', None)
        span_id = getattr(record, 'span_id', None)
        log_record.setdefault('trace_id', trace_id)
        log_record.setdefault('span_id', span_id)
        if trace_id or span_id:
            self._debug("添加追踪信息: trace_id=%s, span_id=%s", trace_id, span_id)

        # 调试输出
        self._debug("日志记录字段列表: %s", list(log_record.keys()))
        if 'method' in log_record:
            self._debug("找到method字段: %s", log_record['method'])
        if 'action' in log_record:
            self._debug("找到action字段: %s", log_record['action'])
        if 'operation' in log_record:
            self._debug("找到operation字段: %s", log_record['operation'])

    def process_log_record(self, log_record):
        """处理日志记录"""
        self._debug("开始处理日志记录，当前字段: %d个", len(log_record))

        # 获取当前时间
        now = self.timezone_formatter.format_time()
        self._debug("当前时间: %s", now)

        # 添加时间字段（不覆盖已有的）
        timestamp_field = self.config.json_timestamp_field
        if timestamp_field not in log_record:
            timestamp_value = self.timezone_formatter.format_timestamp(now)
            log_record[timestamp_field] = timestamp_value
            self._debug("添加时间戳字段: %s = %s", timestamp_field, timestamp_value)

        if 'date' not in log_record:
            date_value = self.timezone_formatter.format_date(now)
            log_record['date'] = date_value
            self._debug("添加日期字段: %s", date_value)

        if 'timezone' not in log_record:
            log_record['timezone'] = self.config.timezone.value
            self._debug("添加时区字段: %s", self.config.timezone.value)

        if 'timestamp_precision' not in log_record:
            log_record['timestamp_precision'] = self.config.timestamp_precision.value
            self._debug("添加精度字段: %s", self.config.timestamp_precision.value)

        # 添加其他标准字段
        if 'environment' not in log_record:
            env = getattr(self.config, 'environment', 'production')
            log_record['environment'] = env
            self._debug("添加环境字段: %s", env)

        if 'service' not in log_record:
            log_record['service'] = self.config.name
            self._debug("添加服务字段: %s", self.config.name)

        if 'hostname' not in log_record:
            hostname = socket.gethostname()
            log_record['hostname'] = hostname
            self._debug("添加主机名字段: %s", hostname)

        if 'pid' not in log_record:
            pid = os.getpid()
            log_record['pid'] = pid
            self._debug("添加进程ID字段: %d", pid)

        # 确保 request_id 字段存在
        if 'request_id' not in log_record:
            log_record['request_id'] = '-'
            self._debug("添加默认request_id: -")

        # 处理异常信息
        if 'exc_info' in log_record and log_record['exc_info']:
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

        # 清理内部字段
        cleaned = 0
        for field in ('exc_info', 'exc_text', 'stack_info', 'args'):
            if field in log_record:
                del log_record[field]
                cleaned += 1
        if cleaned > 0:
            self._debug("清理了 %d 个内部字段", cleaned)

        # 确保所有值都是JSON可序列化的
        serialized_count = 0
        for k, v in list(log_record.items()):
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                log_record[k] = self._safe_json(v)
                serialized_count += 1
        if serialized_count > 0:
            self._debug("对 %d 个字段进行了安全序列化", serialized_count)

        # 调试输出 - 只输出部分字段名，避免过长
        all_keys = list(log_record.keys())
        keys_preview = all_keys[:10]
        if len(all_keys) > 10:
            keys_preview.append(f"... 共{len(all_keys)}个字段")
        self._debug("最终字段预览: %s", keys_preview)

        if 'method' in log_record:
            self._debug("method字段已保留: %s", log_record['method'])

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
        self._debug("初始化 CustomTextFormatter，格式: %s", config.text_format)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.formatter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def formatTime(self, record, datefmt=None):
        """重写时间格式化"""
        created_time = datetime.fromtimestamp(record.created)
        self._debug("格式化时间，原始时间: %s", created_time)

        # 使用时区格式化器获取格式化的时间戳
        formatted_time = self.timezone_formatter.format_timestamp(created_time)
        self._debug("格式化后的时间: %s", formatted_time)

        if isinstance(formatted_time, float):
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

    def format(self, record):
        """格式化日志记录"""
        # 确保有请求ID
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
            self._debug("为日志记录添加默认request_id")
        else:
            self._debug("日志记录已有request_id: %s", record.request_id)

        msg_preview = record.getMessage()
        if len(msg_preview) > 50:
            msg_preview = msg_preview[:50] + "..."
        self._debug("开始格式化文本日志: %s", msg_preview)

        result = super().format(record)
        self._debug("文本日志格式化完成")
        return result