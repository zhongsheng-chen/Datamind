# datamind/config/logging_config.py

"""日志配置模块

定义日志系统的所有配置项，支持环境变量配置和验证。

核心功能：
  - get_log_path: 获取日志文件完整路径（支持时间戳和时区）
  - use_json: 判断是否使用 JSON 格式日志
  - use_text: 判断是否使用文本格式日志
  - to_summary_dict: 获取配置摘要（用于调试）

特性：
  - 多格式支持：支持文本和 JSON 两种日志格式
  - 灵活轮转：支持按大小轮转和按时间轮转
  - 采样控制：支持概率采样和间隔采样（互斥）
  - 敏感脱敏：自动识别并脱敏密码、token 等敏感字段
  - 远程日志：支持 HTTP/HTTPS 远程日志上报
  - 异步日志：队列缓冲，非阻塞写入
  - 日志归档：自动压缩归档过期日志
  - 跨平台：支持 Windows/Linux/macOS 并发锁目录
  - 完整验证：类型、范围、格式、依赖关系全面校验
  - 环境变量支持：支持 DATAMIND_LOG_* 前缀的环境变量
  - 配置摘要：提供 summary 方法便于调试和监控
"""

import os
import re
import json
import logging
import tempfile
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set, List
from pydantic import Field, field_validator, model_validator
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from datamind import PROJECT_ROOT
from .base import BaseConfig, _mask_sensitive


# ==================== 常量定义 ====================

# 大小常量
KB: int = 1024
MB: int = 1024 * KB
GB: int = 1024 * MB

# 文件大小限制
FILE_SIZE_MIN: int = 1 * MB
FILE_SIZE_MAX: int = 10 * GB

# 队列大小限制
ASYNC_QUEUE_SIZE_MIN: int = 100
ASYNC_QUEUE_SIZE_MAX: int = 100000

# 备份文件数量限制
BACKUP_COUNT_MIN: int = 1
BACKUP_COUNT_MAX: int = 365

# 保留天数限制
RETENTION_DAYS_MIN: int = 1
RETENTION_DAYS_MAX: int = 3650

# 采样率精度
SAMPLING_RATE_PRECISION: int = 6

# 时区偏移范围
TIME_OFFSET_HOURS_MIN: int = -12
TIME_OFFSET_HOURS_MAX: int = 14

# 脱敏保留字符数
MASK_PREFIX_LEN: int = 3
MASK_SUFFIX_LEN: int = 3

# 字段名正则
FIELD_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9_.@\-\[\]]+$")
EXTRA_FIELD_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9_]+$")
SENSITIVE_FIELD_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9_]+$")

# 时间格式正则
TIME_FORMAT_PATTERN: re.Pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

# 跨平台并发锁目录
DEFAULT_CONCURRENT_LOCK_DIR: str = os.path.join(tempfile.gettempdir(), "datamind-logs")


class LoggingConstants:
    """日志常量定义

    定义日志系统使用的所有常量。
    """

    KB: int = KB
    MB: int = MB
    GB: int = GB
    FILE_SIZE_MIN: int = FILE_SIZE_MIN
    FILE_SIZE_MAX: int = FILE_SIZE_MAX
    ASYNC_QUEUE_SIZE_MIN: int = ASYNC_QUEUE_SIZE_MIN
    ASYNC_QUEUE_SIZE_MAX: int = ASYNC_QUEUE_SIZE_MAX
    BACKUP_COUNT_MIN: int = BACKUP_COUNT_MIN
    BACKUP_COUNT_MAX: int = BACKUP_COUNT_MAX
    RETENTION_DAYS_MIN: int = RETENTION_DAYS_MIN
    RETENTION_DAYS_MAX: int = RETENTION_DAYS_MAX
    SAMPLING_RATE_PRECISION: int = SAMPLING_RATE_PRECISION
    TIME_OFFSET_HOURS_MIN: int = TIME_OFFSET_HOURS_MIN
    TIME_OFFSET_HOURS_MAX: int = TIME_OFFSET_HOURS_MAX
    MASK_PREFIX_LEN: int = MASK_PREFIX_LEN
    MASK_SUFFIX_LEN: int = MASK_SUFFIX_LEN
    FIELD_PATTERN: re.Pattern = FIELD_PATTERN
    EXTRA_FIELD_PATTERN: re.Pattern = EXTRA_FIELD_PATTERN
    SENSITIVE_FIELD_PATTERN: re.Pattern = SENSITIVE_FIELD_PATTERN
    TIME_FORMAT_PATTERN: re.Pattern = TIME_FORMAT_PATTERN
    DEFAULT_CONCURRENT_LOCK_DIR: str = DEFAULT_CONCURRENT_LOCK_DIR


class LogField:
    """日志字段常量

    定义 JSON 格式日志输出中使用的字段名。
    """

    TIMESTAMP = "@timestamp"
    LEVEL = "level"
    LEVEL_NO = "levelno"
    MESSAGE = "message"
    LOGGER = "logger"
    SERVICE = "service"
    ENVIRONMENT = "environment"
    HOSTNAME = "hostname"
    PID = "pid"
    REQUEST_ID = "request_id"
    TRACE_ID = "trace_id"
    SPAN_ID = "span_id"
    PARENT_SPAN_ID = "parent_span_id"
    MODULE = "module"
    FUNC_NAME = "funcName"
    LINE_NO = "lineno"
    FILE_NAME = "filename"
    PATH_NAME = "pathname"
    THREAD_NAME = "threadName"
    PROCESS_NAME = "processName"
    EXCEPTION_TYPE = "exception.type"
    EXCEPTION_MESSAGE = "exception.message"
    EXCEPTION_STACKTRACE = "exception.stacktrace"
    DURATION_MS = "duration_ms"


VALID_LOGRECORD_FIELDS: Set[str] = {
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module',
    'msecs', 'msg', 'name', 'pathname', 'process', 'processName',
    'relativeCreated', 'stack_info', 'thread', 'threadName'
}


class SensitiveField:
    """敏感字段配置

    定义需要脱敏的字段名称，用于日志输出时的自动脱敏处理。
    """

    DEFAULT_SENSITIVE_KEYS: List[str] = [
        "password", "token", "secret", "api_key", "api_secret",
        "access_token", "refresh_token", "auth_token",
        "credit_card", "card_number", "cvv", "cvc",
        "id_number", "id_card", "ssn", "social_security",
        "private_key", "pem", "certificate"
    ]

    RESERVED_KEYS: Set[str] = {
        LogField.TIMESTAMP, LogField.LEVEL, LogField.LEVEL_NO,
        LogField.MESSAGE, LogField.LOGGER, LogField.SERVICE,
        LogField.ENVIRONMENT, LogField.HOSTNAME, LogField.PID,
        LogField.REQUEST_ID, LogField.TRACE_ID, LogField.SPAN_ID,
        LogField.EXCEPTION_TYPE, LogField.EXCEPTION_MESSAGE,
        LogField.EXCEPTION_STACKTRACE
    }


class LogFormat(str, Enum):
    """日志格式枚举

    - TEXT: 文本格式，便于人工阅读
    - JSON: JSON 格式，便于日志系统采集
    """

    TEXT = "text"
    JSON = "json"


class RotationWhen(str, Enum):
    """日志轮转时间单位

    - S: 秒
    - M: 分钟
    - H: 小时
    - D: 天
    - MIDNIGHT: 每天午夜
    - W0-W6: 每周指定天（W0=周一，W6=周日）
    """

    S = "S"
    M = "M"
    H = "H"
    D = "D"
    MIDNIGHT = "MIDNIGHT"
    W0 = "W0"
    W1 = "W1"
    W2 = "W2"
    W3 = "W3"
    W4 = "W4"
    W5 = "W5"
    W6 = "W6"


class TimestampPrecision(str, Enum):
    """时间戳精度

    - SECONDS: 秒级精度
    - MILLISECONDS: 毫秒级精度
    - MICROSECONDS: 微秒级精度
    - NANOSECONDS: 纳秒级精度
    """

    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class EpochUnit(str, Enum):
    """纪元时间单位

    - SECONDS: 秒
    - MILLISECONDS: 毫秒
    - MICROSECONDS: 微秒
    - NANOSECONDS: 纳秒
    """

    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class RotationStrategy(str, Enum):
    """轮转策略

    - SIZE: 按文件大小轮转
    - TIME: 按时间轮转
    """

    SIZE = "size"
    TIME = "time"


class LoggingConfig(BaseConfig):
    """日志配置

    定义日志系统的所有配置项。

    环境变量前缀：DATAMIND_LOG_
    例如：DATAMIND_LOG_LEVEL=INFO, DATAMIND_LOG_DIR=logs

    属性:
        name: 日志记录器名称
        level: 日志级别（使用 logging 模块常量）
        format: 日志格式（文本/JSON）
        log_dir: 日志目录（支持相对路径和绝对路径）
        log_file: 日志文件名
        file_name_timestamp: 文件名是否包含时间戳
        file_name_date_format: 文件名日期格式
        rotation_strategy: 轮转策略（按大小/按时间）
        sampling_rate/sampling_interval: 采样配置（互斥）
        mask_sensitive: 是否启用敏感信息脱敏
        enable_remote: 是否启用远程日志
        use_async: 是否启用异步日志
        archive_enabled: 是否启用日志归档
    """
    model_config = {"validate_assignment": True, "populate_by_name": True}

    __env_prefix__ = "DATAMIND_LOG_"

    __enum_mappings__ = {
        "format": LogFormat,
        "rotation_when": RotationWhen,
        "rotation_strategy": RotationStrategy,
        "timestamp_precision": TimestampPrecision,
        "json_epoch_unit": EpochUnit,
    }

    # 基本配置
    name: str = Field(default="datamind", alias="NAME", description="日志记录器名称")
    level: int = Field(default=logging.INFO, alias="LEVEL", description="日志级别")
    encoding: str = Field(default="utf-8", alias="ENCODING", description="日志文件编码")

    # 时间格式配置
    timezone: str = Field(default="UTC", alias="TIMEZONE", description="时区名称")
    time_offset_hours: int = Field(default=0, alias="TIME_OFFSET_HOURS", description="日志时间偏移小时数")
    timestamp_precision: TimestampPrecision = Field(
        default=TimestampPrecision.MILLISECONDS,
        alias="TIMESTAMP_PRECISION",
        description="时间戳精度"
    )

    # 文本日志时间格式
    text_date_format: str = Field(default="%Y-%m-%d %H:%M:%S", alias="TEXT_DATE_FORMAT", description="文本日志日期格式")
    text_datetime_format: str = Field(default="%Y-%m-%d %H:%M:%S.%f", alias="TEXT_DATETIME_FORMAT", description="文本日志日期时间格式")

    # JSON日志时间格式
    json_timestamp_field: str = Field(default=LogField.TIMESTAMP, alias="JSON_TIMESTAMP_FIELD", description="JSON日志时间戳字段名")
    json_datetime_format: str = Field(default="%Y-%m-%dT%H:%M:%S.%f%z", alias="JSON_DATETIME_FORMAT", description="JSON日志日期时间格式")
    json_use_epoch: bool = Field(default=False, alias="JSON_USE_EPOCH", description="是否使用纪元时间戳")
    json_epoch_unit: EpochUnit = Field(default=EpochUnit.MILLISECONDS, alias="JSON_EPOCH_UNIT", description="纪元时间戳单位")

    # 日志文件名时间格式
    file_name_timestamp: bool = Field(default=True, alias="FILE_NAME_TIMESTAMP", description="文件名是否包含时间戳")
    file_name_date_format: str = Field(default="%Y%m%d", alias="FILE_NAME_DATE_FORMAT", description="文件名日期格式")

    # 日志目录和文件
    log_dir: str = Field(default="logs", alias="DIR", description="日志目录（支持相对路径和绝对路径）")
    log_file: str = Field(default="datamind.log", alias="FILE", description="日志文件名")

    # 日志格式
    format: LogFormat = Field(default=LogFormat.JSON, alias="FORMAT", description="日志格式")
    text_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
        alias="TEXT_FORMAT",
        description="文本日志格式"
    )
    json_format: Dict[str, str] = Field(
        default_factory=lambda: {
            LogField.TIMESTAMP: "asctime",
            "log.level": "levelname",
            "log.logger": "name",
            LogField.MESSAGE: "message",
            "trace.id": "extra.request_id",
            "source.file": "filename",
            "source.line": "lineno",
            "process.pid": "process",
        },
        alias="JSON_FORMAT",
        description="JSON日志字段映射"
    )

    # 文件轮转配置（按大小）
    max_bytes: int = Field(default=100 * MB, alias="MAX_BYTES", description="单个日志文件最大字节数")
    backup_count: int = Field(default=30, alias="BACKUP_COUNT", description="备份文件数量")

    # 时间轮转配置
    rotation_strategy: RotationStrategy = Field(default=RotationStrategy.TIME, alias="ROTATION_STRATEGY", description="轮转策略")
    rotation_when: Optional[RotationWhen] = Field(default=RotationWhen.MIDNIGHT, alias="ROTATION_WHEN", description="时间轮转单位")
    rotation_interval: int = Field(default=1, alias="ROTATION_INTERVAL", description="时间轮转间隔")
    rotation_at_time: Optional[str] = Field(default=None, alias="ROTATION_AT_TIME", description="指定轮转时间（HH:MM格式）")
    rotation_utc: bool = Field(default=False, alias="ROTATION_UTC", description="是否使用UTC时间轮转")

    # 旧日志清理
    retention_days: int = Field(default=90, alias="RETENTION_DAYS", description="日志保留天数")
    cleanup_at_time: str = Field(default="03:00", alias="CLEANUP_AT_TIME", description="清理时间（HH:MM格式）")

    # 并发处理
    use_concurrent: bool = Field(default=True, alias="USE_CONCURRENT", description="是否启用并发日志")
    concurrent_lock_dir: str = Field(default=DEFAULT_CONCURRENT_LOCK_DIR, alias="CONCURRENT_LOCK_DIR", description="并发锁目录")

    # 异步日志
    use_async: bool = Field(default=False, alias="USE_ASYNC", description="是否启用异步日志")
    async_queue_size: int = Field(default=10000, alias="ASYNC_QUEUE_SIZE", description="异步队列大小")

    # 日志采样
    sampling_rate: float = Field(default=1.0, alias="SAMPLING_RATE", description="日志采样率 (0-1)")
    sampling_interval: int = Field(default=0, alias="SAMPLING_INTERVAL", description="日志采样间隔（秒），0表示不使用间隔采样")

    # 敏感信息脱敏
    mask_sensitive: bool = Field(default=True, alias="MASK_SENSITIVE", description="是否启用敏感信息脱敏")
    sensitive_fields: Set[str] = Field(
        default_factory=lambda: set(SensitiveField.DEFAULT_SENSITIVE_KEYS),
        alias="SENSITIVE_FIELDS",
        description="敏感字段列表"
    )
    mask_char: str = Field(default="*", alias="MASK_CHAR", description="脱敏字符")

    # 远程日志
    enable_remote: bool = Field(default=False, alias="ENABLE_REMOTE", description="是否启用远程日志")
    remote_url: Optional[str] = Field(default=None, alias="REMOTE_URL", description="远程日志URL")
    remote_token: Optional[str] = Field(default=None, alias="REMOTE_TOKEN", description="远程日志认证令牌")
    remote_timeout: int = Field(default=5, alias="REMOTE_TIMEOUT", description="远程日志超时时间（秒）")
    remote_batch_size: int = Field(default=100, alias="REMOTE_BATCH_SIZE", description="远程日志批处理大小")

    # 控制台输出
    console_output: bool = Field(default=True, alias="CONSOLE_OUTPUT", description="是否输出到控制台")
    console_level: int = Field(default=logging.INFO, alias="CONSOLE_LEVEL", description="控制台日志级别")

    # 归档配置
    archive_enabled: bool = Field(default=False, alias="ARCHIVE_ENABLED", description="是否启用日志归档")
    archive_path: str = Field(default="archive", alias="ARCHIVE_PATH", description="归档路径")
    archive_compression: str = Field(default="gz", alias="ARCHIVE_COMPRESSION", description="归档压缩格式")
    archive_name_format: str = Field(default="%Y%m%d_%H%M%S", alias="ARCHIVE_NAME_FORMAT", description="归档文件名时间格式")

    # ==================== 私有方法 ====================

    def _now(self) -> datetime:
        """获取当前日志时间（考虑时区和偏移）

        返回:
            应用时区和偏移后的当前时间
        """
        try:
            now = datetime.now(ZoneInfo(self.timezone))
        except ZoneInfoNotFoundError:
            now = datetime.now(ZoneInfo("UTC"))

        if self.time_offset_hours != 0:
            now += timedelta(hours=self.time_offset_hours)

        return now

    # ==================== 字段验证器 ====================

    @field_validator('level', 'console_level', mode='before')
    @classmethod
    def coerce_log_level(cls, v):
        """转换日志级别值"""
        if isinstance(v, int):
            if v not in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
                raise ValueError(f"无效的日志级别数字: {v}，必须是 10/20/30/40/50")
            return v

        if isinstance(v, str):
            level = logging.getLevelName(v.upper())
            if isinstance(level, int):
                return level

        raise ValueError(f"无效的日志级别: {v}")

    @field_validator('sampling_rate')
    @classmethod
    def validate_sampling_rate(cls, v: float) -> float:
        """验证采样率在有效范围内"""
        if v < 0 or v > 1:
            raise ValueError("采样率必须在0到1之间")
        return round(v, SAMPLING_RATE_PRECISION)

    @field_validator('max_bytes')
    @classmethod
    def validate_max_bytes(cls, v: int) -> int:
        """验证最大文件大小在有效范围内"""
        if v < FILE_SIZE_MIN:
            raise ValueError(f"max_bytes 不能小于 {FILE_SIZE_MIN // MB}MB")
        if v > FILE_SIZE_MAX:
            raise ValueError(f"max_bytes 不能大于 {FILE_SIZE_MAX // GB}GB")
        return v

    @field_validator('backup_count')
    @classmethod
    def validate_backup_count(cls, v: int) -> int:
        """验证备份文件数量在有效范围内"""
        if v < BACKUP_COUNT_MIN:
            raise ValueError(f"backup_count 不能小于 {BACKUP_COUNT_MIN}")
        if v > BACKUP_COUNT_MAX:
            raise ValueError(f"backup_count 不能大于 {BACKUP_COUNT_MAX}")
        return v

    @field_validator('retention_days')
    @classmethod
    def validate_retention_days(cls, v: int) -> int:
        """验证保留天数在有效范围内"""
        if v < RETENTION_DAYS_MIN:
            raise ValueError(f"retention_days 不能小于 {RETENTION_DAYS_MIN}")
        if v > RETENTION_DAYS_MAX:
            raise ValueError(f"retention_days 不能大于 {RETENTION_DAYS_MAX}")
        return v

    @field_validator('async_queue_size')
    @classmethod
    def validate_async_queue_size(cls, v: int) -> int:
        """验证异步队列大小在有效范围内"""
        if v < ASYNC_QUEUE_SIZE_MIN:
            raise ValueError(f"async_queue_size 不能小于 {ASYNC_QUEUE_SIZE_MIN}")
        if v > ASYNC_QUEUE_SIZE_MAX:
            raise ValueError(f"async_queue_size 不能大于 {ASYNC_QUEUE_SIZE_MAX}")
        return v

    @field_validator('time_offset_hours')
    @classmethod
    def validate_time_offset_hours(cls, v: int) -> int:
        """验证时区偏移在有效范围内"""
        if v < TIME_OFFSET_HOURS_MIN or v > TIME_OFFSET_HOURS_MAX:
            raise ValueError(f"time_offset_hours 必须在 {TIME_OFFSET_HOURS_MIN} 到 {TIME_OFFSET_HOURS_MAX} 之间")
        return v

    @field_validator('json_timestamp_field')
    @classmethod
    def validate_json_timestamp_field(cls, v: str) -> str:
        """验证 JSON 时间戳字段名合法性"""
        if not FIELD_PATTERN.match(v):
            raise ValueError(f"json_timestamp_field 不合法: {v}")
        return v

    @field_validator("json_format", mode="before")
    @classmethod
    def validate_json_format(cls, v):
        """验证 JSON 格式配置"""
        if v is None:
            return v

        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON 格式配置不是合法 JSON: {e}")

        if not isinstance(v, dict):
            raise ValueError("json_format 必须是 dict")

        result = {}
        for k, val in v.items():
            key = str(k)
            value = str(val)

            if key in SensitiveField.RESERVED_KEYS:
                raise ValueError(f"json_format 不允许覆盖保留字段: {key}")

            if not FIELD_PATTERN.match(key):
                raise ValueError(f"json_format key 不合法: {key}")

            if value.startswith("extra."):
                parts = value.split(".")
                if len(parts) < 2:
                    raise ValueError(f"extra 字段格式错误: {value}")
                for part in parts[1:]:
                    if not EXTRA_FIELD_PATTERN.match(part):
                        raise ValueError(f"extra 字段名不合法: {part}")
            else:
                if value not in VALID_LOGRECORD_FIELDS:
                    raise ValueError(f"json_format value 不合法: {value}")

            result[key] = value

        if not result:
            raise ValueError("json_format 不能为空")

        return result

    @field_validator('sensitive_fields')
    @classmethod
    def validate_sensitive_fields(cls, v: Set[str]) -> Set[str]:
        """验证敏感字段列表"""
        for field in v:
            if not field or not field.strip():
                raise ValueError("敏感字段不能为空字符串")
            if not SENSITIVE_FIELD_PATTERN.match(field):
                raise ValueError(f"敏感字段名只能包含字母、数字和下划线: {field}")
        return v

    @field_validator('mask_char')
    @classmethod
    def validate_mask_char(cls, v: str) -> str:
        """验证脱敏字符"""
        if len(v) != 1:
            raise ValueError("mask_char 必须是单个字符")
        if v.isspace():
            raise ValueError("mask_char 不能是空白字符")
        return v

    @field_validator('rotation_at_time')
    @classmethod
    def validate_rotation_at_time(cls, v: Optional[str]) -> Optional[str]:
        """验证轮转时间格式"""
        if v is not None:
            if not TIME_FORMAT_PATTERN.match(v):
                raise ValueError("rotation_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('cleanup_at_time')
    @classmethod
    def validate_cleanup_at_time(cls, v: str) -> str:
        """验证清理时间格式"""
        if not TIME_FORMAT_PATTERN.match(v):
            raise ValueError("cleanup_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('log_dir')
    @classmethod
    def validate_log_dir(cls, v: str) -> str:
        """验证日志目录

        支持相对路径和绝对路径：
            - 相对路径：相对于项目根目录
            - 绝对路径：直接使用
        """
        if not v or v.strip() == "":
            raise ValueError("log_dir 不能为空")

        p = Path(v)

        if ".." in p.parts:
            raise ValueError("log_dir 不能包含 ..")

        return v

    @field_validator('concurrent_lock_dir')
    @classmethod
    def validate_concurrent_lock_dir(cls, v: str) -> str:
        """验证并发锁目录"""
        if not v or v.strip() == "":
            raise ValueError("concurrent_lock_dir 不能为空")

        p = Path(v)
        if ".." in p.parts:
            raise ValueError("concurrent_lock_dir 不能包含 ..")

        return v

    @field_validator('archive_compression')
    @classmethod
    def validate_archive_compression(cls, v: str) -> str:
        """验证归档压缩格式"""
        valid_formats = ["gz", "bz2", "xz"]
        if v not in valid_formats:
            raise ValueError(f"不支持的归档压缩格式: {v}，支持 {valid_formats}")
        return v

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """验证时区值"""
        if not v:
            raise ValueError("timezone 不能为空")

        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"时区无效: {v}，请使用 UTC 或 IANA 时区格式，如 Asia/Shanghai")

        return v

    @field_validator('remote_token')
    @classmethod
    def validate_remote_token(cls, v: Optional[str]) -> Optional[str]:
        """验证远程日志令牌"""
        if v is not None and len(v) < 8:
            raise ValueError("remote_token 长度不能少于8位")
        return v

    # ==================== 模型验证器 ====================

    @model_validator(mode='after')
    def validate_remote_config(self):
        """验证远程日志配置"""
        if self.enable_remote:
            if not self.remote_url:
                raise ValueError("启用远程日志时必须提供 remote_url")

            try:
                parsed = urlparse(self.remote_url)
                if parsed.scheme not in ("http", "https"):
                    raise ValueError(f"不支持的 URL 协议: {parsed.scheme}，仅支持 http/https")
                if not parsed.netloc:
                    raise ValueError(f"URL 缺少主机名: {self.remote_url}")
            except Exception as e:
                raise ValueError(f"remote_url 格式无效: {e}")

        return self

    @model_validator(mode='after')
    def validate_rotation_strategy(self):
        """验证轮转策略配置"""
        if self.rotation_strategy == RotationStrategy.TIME:
            if not self.rotation_when:
                raise ValueError("rotation_strategy=TIME 必须配置 rotation_when")
            if self.rotation_interval < 1:
                raise ValueError("rotation_interval 必须 >= 1")

        elif self.rotation_strategy == RotationStrategy.SIZE:
            if self.max_bytes <= 0:
                raise ValueError("rotation_strategy=SIZE 必须配置 max_bytes > 0")

        return self

    @model_validator(mode='after')
    def validate_json_timestamp(self):
        """验证 JSON 时间戳字段"""
        if self.use_json():
            if not self.json_timestamp_field:
                raise ValueError("json_timestamp_field 不能为空")
            if self.json_timestamp_field not in self.json_format:
                raise ValueError(
                    f"json_format 必须包含时间字段 {self.json_timestamp_field}，"
                    f"当前字段: {list(self.json_format.keys())}"
                )
        return self

    @model_validator(mode='after')
    def validate_archive_config(self):
        """验证归档配置"""
        if self.archive_enabled:
            if not self.archive_path or self.archive_path.strip() == "":
                raise ValueError("启用归档时必须提供 archive_path")
        return self

    @model_validator(mode='after')
    def validate_sampling(self):
        """验证采样配置一致性

        采样支持三种模式，互斥：
          - 不采样：sampling_rate=1.0, sampling_interval=0
          - 概率采样：sampling_rate < 1.0, sampling_interval=0
          - 间隔采样：sampling_interval > 0, sampling_rate=1.0
        """
        if self.sampling_rate == 0 and self.sampling_interval == 0:
            raise ValueError("sampling_rate=0 且 sampling_interval=0 会丢弃所有日志，请至少启用一种采样方式")

        if self.sampling_rate < 1.0 and self.sampling_interval > 0:
            raise ValueError(
                "sampling_rate 和 sampling_interval 不能同时使用。"
                "请选择概率采样（设置 sampling_rate < 1.0）或间隔采样（设置 sampling_interval > 0）"
            )
        return self

    @model_validator(mode='after')
    def validate_console_level(self):
        """验证控制台日志级别"""
        if self.console_level < self.level:
            object.__setattr__(self, "console_level", self.level)
        return self

    # ==================== 公共方法 ====================

    def get_log_path(self) -> Path:
        """获取日志文件完整路径（支持时间戳和时区）

        支持：
            - 相对路径：相对于项目根目录
            - 绝对路径：直接使用

        返回:
            日志文件的 Path 对象
        """
        filename = self.log_file

        if self.file_name_timestamp:
            ts = self._now().strftime(self.file_name_date_format)
            name, ext = os.path.splitext(self.log_file)
            filename = f"{name}.{ts}{ext}"

        dir_path = Path(self.log_dir)

        if dir_path.is_absolute():
            return dir_path / filename
        else:
            return PROJECT_ROOT / self.log_dir / filename

    def use_json(self) -> bool:
        """是否使用 JSON 格式日志

        返回:
            True 表示使用 JSON 格式，False 表示使用文本格式
        """
        return self.format == LogFormat.JSON

    def use_text(self) -> bool:
        """是否使用文本格式日志

        返回:
            True 表示使用文本格式，False 表示使用 JSON 格式
        """
        return self.format == LogFormat.TEXT

    def to_summary_dict(self) -> Dict[str, Any]:
        """获取配置摘要（用于调试和监控）

        返回:
            配置摘要字典，包含关键配置项
        """
        return {
            "name": self.name,
            "level": self.level,
            "level_name": logging.getLevelName(self.level),
            "format": self.format.value,
            "log_dir": self.log_dir,
            "log_dir_absolute": str(Path(self.log_dir)) if Path(self.log_dir).is_absolute() else str(PROJECT_ROOT / self.log_dir),
            "log_file": self.log_file,
            "file_name_timestamp": self.file_name_timestamp,
            "use_async": self.use_async,
            "async_queue_size": self.async_queue_size if self.use_async else None,
            "rotation_strategy": self.rotation_strategy.value,
            "rotation_when": self.rotation_when.value if self.rotation_when else None,
            "retention_days": self.retention_days,
            "mask_sensitive": self.mask_sensitive,
            "mask_char": self.mask_char,
            "console_output": self.console_output,
            "console_level": self.console_level,
            "console_level_name": logging.getLevelName(self.console_level),
            "enable_remote": self.enable_remote,
            "remote_url": self.remote_url if self.enable_remote else None,
            "remote_token": _mask_sensitive(self.remote_token, "remote_token") if self.enable_remote else None,
            "archive_enabled": self.archive_enabled,
            "timezone": self.timezone,
            "time_offset_hours": self.time_offset_hours,
        }


__all__ = [
    "LoggingConfig",
    "LogFormat",
    "RotationWhen",
    "TimestampPrecision",
    "EpochUnit",
    "RotationStrategy",
    "LogField",
    "SensitiveField",
    "LoggingConstants",
]