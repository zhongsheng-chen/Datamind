# datamind/config/logging_config.py

"""日志配置模块

定义日志系统的所有配置项，支持环境变量配置和验证。

核心功能：
  - 日志级别配置（DEBUG/INFO/WARNING/ERROR/CRITICAL）
  - 日志格式配置（文本/JSON/双格式）
  - 日志轮转配置（按大小/按时间）
  - 日志采样配置（采样率、采样间隔）
  - 敏感信息脱敏配置
  - 日志分类配置（访问日志/审计日志/性能日志）
  - 远程日志配置
  - 异步日志配置
  - 日志归档配置

配置来源：
  支持从环境变量读取配置


配置验证：
  提供完善的配置验证，包括：
    - 类型验证（枚举、整数、字符串）
    - 范围验证（采样率0-1、保留天数>0）
    - 格式验证（时间格式、正则表达式）
    - 依赖验证（远程日志需要URL、时间轮转需要when）

枚举类型：
  - LogLevel: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
  - LogFormat: 日志格式（text/json/both）
  - RotationWhen: 轮转时间单位（S/M/H/D/MIDNIGHT/W0-W6）
  - TimeZone: 时区（UTC/LOCAL/CST/EST/PST）
  - TimestampPrecision: 时间戳精度（seconds/milliseconds/microseconds/nanoseconds）
  - EpochUnit: 纪元时间单位（seconds/milliseconds/microseconds/nanoseconds）
  - RotationStrategy: 轮转策略（size/time）

日志字段常量（LogField）：
  定义日志输出字段的标准化名称，避免魔法字符串，确保 ELK/Loki 等日志系统能够正确解析。
"""

import re
import json
import logging
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ==================== 日志字段常量 ====================

class LogField:
    """日志字段常量"""

    # 核心字段
    TIMESTAMP = "@timestamp"                       # ISO8601 时间戳（带时区）
    LEVEL = "level"                                # 日志级别 (INFO/ERROR)
    LEVEL_NO = "levelno"                           # 日志级别数字 (20/40)
    MESSAGE = "message"                            # 日志内容
    LOGGER = "logger"                              # logger 名称

    # 运行环境字段
    SERVICE = "service"                            # 服务名称
    ENVIRONMENT = "environment"                    # 环境 (dev/test/prod)
    HOSTNAME = "hostname"                          # 主机名
    PID = "pid"                                    # 进程ID

    # 请求链路字段
    REQUEST_ID = "request_id"                      # 请求ID
    TRACE_ID = "trace_id"                          # 链路追踪ID
    SPAN_ID = "span_id"                            # Span ID
    PARENT_SPAN_ID = "parent_span_id"              # 父Span ID

    # 代码位置字段（调试用）
    MODULE = "module"                              # 模块名
    FUNC_NAME = "funcName"                         # 函数名
    LINE_NO = "lineno"                             # 行号
    FILE_NAME = "filename"                         # 文件名
    PATH_NAME = "pathname"                         # 文件路径

    # 线程/进程字段
    THREAD_NAME = "threadName"                     # 线程名
    PROCESS_NAME = "processName"                   # 进程名

    # 异常字段
    EXCEPTION_TYPE = "exception.type"              # 异常类型
    EXCEPTION_MESSAGE = "exception.message"        # 异常消息
    EXCEPTION_STACKTRACE = "exception.stacktrace"  # 异常堆栈

    # 性能字段
    DURATION_MS = "duration_ms"  # 耗时（毫秒）


# ==================== 敏感字段配置 ====================

class SensitiveField:
    """敏感字段配置

    定义需要脱敏的字段名称，用于日志输出时的自动脱敏处理。
    """

    # 默认敏感字段列表
    DEFAULT_SENSITIVE_KEYS = [
        "password", "token", "secret", "api_key", "api_secret",
        "access_token", "refresh_token", "auth_token",
        "credit_card", "card_number", "cvv", "cvc",
        "id_number", "id_card", "ssn", "social_security",
        "private_key", "pem", "certificate"
    ]

    # 系统保留字段（不允许被 extra 覆盖）
    RESERVED_KEYS = {
        LogField.TIMESTAMP, LogField.LEVEL, LogField.LEVEL_NO,
        LogField.MESSAGE, LogField.LOGGER, LogField.SERVICE,
        LogField.ENVIRONMENT, LogField.HOSTNAME, LogField.PID,
        LogField.REQUEST_ID, LogField.TRACE_ID, LogField.SPAN_ID,
        LogField.EXCEPTION_TYPE, LogField.EXCEPTION_MESSAGE,
        LogField.EXCEPTION_STACKTRACE
    }


# ==================== 枚举定义 ====================

class LogLevel(int, Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(str, Enum):
    """日志格式枚举"""
    TEXT = "text"
    JSON = "json"
    BOTH = "both"


class RotationWhen(str, Enum):
    """日志轮转时间单位"""
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


class TimeZone(str, Enum):
    """时区枚举"""
    UTC = "UTC"
    LOCAL = "LOCAL"
    CST = "CST"
    EST = "EST"
    PST = "PST"


class TimestampPrecision(str, Enum):
    """时间戳精度"""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class EpochUnit(str, Enum):
    """纪元时间单位"""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class RotationStrategy(str, Enum):
    """轮转策略"""
    SIZE = "size"
    TIME = "time"


# ==================== 验证常量 ====================

VALID_LOGRECORD_FIELDS = {
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module',
    'msecs', 'msg', 'name', 'pathname', 'process', 'processName',
    'relativeCreated', 'stack_info', 'thread', 'threadName'
}

FIELD_PATTERN = re.compile(r"^[a-zA-Z0-9_.@\-\[\]]+$")


# ==================== 日志配置 ====================

class LoggingConfig(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # 基本配置
    name: str = Field(
        default="datamind",
        validation_alias="DATAMIND_LOG_NAME",
        description="日志记录器名称"
    )
    level: LogLevel = Field(
        default=LogLevel.INFO,
        validation_alias="DATAMIND_LOG_LEVEL",
        description="日志级别"
    )
    encoding: str = Field(
        default="utf-8",
        validation_alias="DATAMIND_LOG_ENCODING",
        description="日志文件编码"
    )

    # 采样配置（高并发场景）
    sample_rate: float = Field(
        default=1.0,
        validation_alias="DATAMIND_LOG_SAMPLE_RATE",
        description="日志采样率 (0.0-1.0)，1.0 表示记录所有日志"
    )

    # 调试配置
    manager_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_MANAGER_DEBUG",
        description="管理器调试模式"
    )
    formatter_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FORMATTER_DEBUG",
        description="格式化器调试模式"
    )
    handler_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_HANDLER_DEBUG",
        description="处理器调试模式"
    )
    filter_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FILTER_DEBUG",
        description="过滤器调试模式"
    )
    context_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CONTEXT_DEBUG",
        description="上下文调试模式"
    )
    cleanup_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CLEANUP_DEBUG",
        description="清理调试模式"
    )

    # 时间格式配置
    timezone: TimeZone = Field(
        default=TimeZone.UTC,
        validation_alias="DATAMIND_LOG_TIMEZONE",
        description="时区"
    )
    time_offset_hours: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_TIME_OFFSET_HOURS",
        description="日志时间偏移小时数"
    )
    timestamp_precision: TimestampPrecision = Field(
        default=TimestampPrecision.MILLISECONDS,
        validation_alias="DATAMIND_LOG_TIMESTAMP_PRECISION",
        description="时间戳精度"
    )

    # 文本日志时间格式
    text_date_format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        validation_alias="DATAMIND_TEXT_DATE_FORMAT",
        description="文本日志日期格式"
    )
    text_datetime_format: str = Field(
        default="%Y-%m-%d %H:%M:%S.%f",
        validation_alias="DATAMIND_TEXT_DATETIME_FORMAT",
        description="文本日志日期时间格式"
    )

    # JSON日志时间格式
    json_timestamp_field: str = Field(
        default=LogField.TIMESTAMP,
        validation_alias="DATAMIND_JSON_TIMESTAMP_FIELD",
        description="JSON日志时间戳字段名"
    )
    json_datetime_format: str = Field(
        default="yyyy-MM-dd'T'HH:mm:ss.SSSZ",
        validation_alias="DATAMIND_JSON_DATETIME_FORMAT",
        description="JSON日志日期时间格式（Java风格）"
    )
    json_use_epoch: bool = Field(
        default=False,
        validation_alias="DATAMIND_JSON_USE_EPOCH",
        description="是否使用纪元时间戳"
    )
    json_epoch_unit: EpochUnit = Field(
        default=EpochUnit.MILLISECONDS,
        validation_alias="DATAMIND_JSON_EPOCH_UNIT",
        description="纪元时间戳单位"
    )

    # 日志文件名时间格式
    file_name_timestamp: bool = Field(
        default=True,
        validation_alias="DATAMIND_FILE_NAME_TIMESTAMP",
        description="文件名是否包含时间戳"
    )
    file_name_date_format: str = Field(
        default="%Y%m%d",
        validation_alias="DATAMIND_FILE_NAME_DATE_FORMAT",
        description="文件名日期格式"
    )

    # BOTH 格式文件后缀配置
    text_suffix: str = Field(
        default="text",
        validation_alias="DATAMIND_TEXT_SUFFIX",
        description="BOTH格式文本文件后缀"
    )
    json_suffix: str = Field(
        default="json",
        validation_alias="DATAMIND_JSON_SUFFIX",
        description="BOTH格式JSON文件后缀"
    )

    # 日志目录配置
    log_dir: str = Field(
        default="logs",
        validation_alias="DATAMIND_LOG_DIR",
        description="日志目录"
    )

    # 文件配置
    file: str = Field(
        default="datamind.log",
        validation_alias="DATAMIND_LOG_FILE",
        description="主日志文件名"
    )
    error_file: Optional[str] = Field(
        default="datamind.error.log",
        validation_alias="DATAMIND_ERROR_LOG_FILE",
        description="错误日志文件名"
    )

    # 日志格式
    format: LogFormat = Field(
        default=LogFormat.JSON,
        validation_alias="DATAMIND_LOG_FORMAT",
        description="日志格式"
    )
    text_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
        validation_alias="DATAMIND_TEXT_FORMAT",
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
        validation_alias="DATAMIND_JSON_FORMAT",
        description="JSON日志字段映射"
    )

    # 文件轮转配置（按大小）
    max_bytes: int = Field(
        default=104857600,  # 100MB
        validation_alias="DATAMIND_LOG_MAX_BYTES",
        description="单个日志文件最大字节数"
    )
    backup_count: int = Field(
        default=30,
        validation_alias="DATAMIND_LOG_BACKUP_COUNT",
        description="备份文件数量"
    )

    # 时间轮转配置
    rotation_strategy: RotationStrategy = Field(
        default=RotationStrategy.TIME,
        validation_alias="DATAMIND_LOG_ROTATION_STRATEGY",
        description="轮转策略"
    )
    rotation_when: Optional[RotationWhen] = Field(
        default=RotationWhen.MIDNIGHT,
        validation_alias="DATAMIND_LOG_ROTATION_WHEN",
        description="时间轮转单位"
    )
    rotation_interval: int = Field(
        default=1,
        validation_alias="DATAMIND_LOG_ROTATION_INTERVAL",
        description="时间轮转间隔"
    )
    rotation_at_time: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_ROTATION_AT_TIME",
        description="指定轮转时间（HH:MM格式）"
    )
    rotation_utc: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ROTATION_UTC",
        description="是否使用UTC时间轮转"
    )

    # 旧日志清理
    retention_days: int = Field(
        default=90,
        validation_alias="DATAMIND_LOG_RETENTION_DAYS",
        description="日志保留天数"
    )
    cleanup_at_time: str = Field(
        default="03:00",
        validation_alias="DATAMIND_LOG_CLEANUP_AT_TIME",
        description="清理时间（HH:MM格式）"
    )

    # 并发处理
    use_concurrent: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_USE_CONCURRENT",
        description="是否启用并发日志"
    )
    concurrent_lock_dir: str = Field(
        default="/tmp/datamind-logs",
        validation_alias="DATAMIND_LOG_LOCK_DIR",
        description="并发锁目录"
    )

    # 异步日志
    use_async: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ASYNC",
        description="是否启用异步日志"
    )
    async_queue_size: int = Field(
        default=10000,
        validation_alias="DATAMIND_LOG_QUEUE_SIZE",
        description="异步队列大小"
    )

    # 日志采样
    sampling_rate: float = Field(
        default=1.0,
        validation_alias="DATAMIND_LOG_SAMPLING_RATE",
        description="日志采样率 (0-1)"
    )
    sampling_interval: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_SAMPLING_INTERVAL",
        description="日志采样间隔（秒），0表示不使用间隔采样"
    )

    # 敏感信息脱敏
    mask_sensitive: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_MASK_SENSITIVE",
        description="是否启用敏感信息脱敏"
    )
    sensitive_fields: Set[str] = Field(
        default_factory=lambda: set(SensitiveField.DEFAULT_SENSITIVE_KEYS),
        validation_alias="DATAMIND_SENSITIVE_FIELDS",
        description="敏感字段列表"
    )
    mask_char: str = Field(
        default="*",
        validation_alias="DATAMIND_LOG_MASK_CHAR",
        description="脱敏字符"
    )

    # 日志分类
    enable_access_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ACCESS",
        description="是否启用访问日志"
    )
    access_log_file: str = Field(
        default="datamind.access.log",
        validation_alias="DATAMIND_ACCESS_LOG_FILE",
        description="访问日志文件名"
    )

    enable_audit_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_AUDIT",
        description="是否启用审计日志"
    )
    audit_log_file: str = Field(
        default="datamind.audit.log",
        validation_alias="DATAMIND_AUDIT_LOG_FILE",
        description="审计日志文件名"
    )

    enable_performance_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_PERFORMANCE",
        description="是否启用性能日志"
    )
    performance_log_file: str = Field(
        default="datamind.performance.log",
        validation_alias="DATAMIND_PERFORMANCE_LOG_FILE",
        description="性能日志文件名"
    )

    # 日志过滤
    filters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_paths": ["/health", "/metrics"],
            "exclude_status_codes": [404],
            "min_duration_ms": 0
        },
        validation_alias="DATAMIND_LOG_FILTERS",
        description="日志过滤配置"
    )

    # 远程日志
    enable_remote: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_REMOTE",
        description="是否启用远程日志"
    )
    remote_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_URL",
        description="远程日志URL"
    )
    remote_token: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_TOKEN",
        description="远程日志认证令牌"
    )
    remote_timeout: int = Field(
        default=5,
        validation_alias="DATAMIND_LOG_REMOTE_TIMEOUT",
        description="远程日志超时时间（秒）"
    )
    remote_batch_size: int = Field(
        default=100,
        validation_alias="DATAMIND_LOG_REMOTE_BATCH_SIZE",
        description="远程日志批处理大小"
    )

    # 控制台输出
    console_output: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_CONSOLE",
        description="是否输出到控制台"
    )
    console_level: LogLevel = Field(
        default=LogLevel.INFO,
        validation_alias="DATAMIND_LOG_CONSOLE_LEVEL",
        description="控制台日志级别"
    )

    # 归档配置
    archive_enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ARCHIVE",
        description="是否启用日志归档"
    )
    archive_path: str = Field(
        default="archive",
        validation_alias="DATAMIND_LOG_ARCHIVE_PATH",
        description="归档路径"
    )
    archive_compression: str = Field(
        default="gz",
        validation_alias="DATAMIND_LOG_COMPRESSION",
        description="归档压缩格式"
    )
    archive_name_format: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_ARCHIVE_NAME_FORMAT",
        description="归档文件名时间格式"
    )

    @field_validator('level', 'console_level', mode='before')
    @classmethod
    def coerce_log_level(cls, v):
        if isinstance(v, LogLevel):
            return v
        if isinstance(v, int):
            try:
                return LogLevel(v)
            except ValueError:
                return LogLevel.INFO
        if isinstance(v, str):
            level_map = {
                "DEBUG": LogLevel.DEBUG,
                "INFO": LogLevel.INFO,
                "WARNING": LogLevel.WARNING,
                "ERROR": LogLevel.ERROR,
                "CRITICAL": LogLevel.CRITICAL,
            }
            return level_map.get(v.upper(), LogLevel.INFO)
        return LogLevel.INFO

    @field_validator('sampling_rate')
    @classmethod
    def validate_sampling_rate(cls, v):
        if v < 0 or v > 1:
            raise ValueError("采样率必须在0到1之间")
        return v

    @field_validator('max_bytes')
    @classmethod
    def validate_max_bytes(cls, v):
        if v < 0:
            raise ValueError("max_bytes 不能为负数")
        return v

    @field_validator("json_format", mode="before")
    @classmethod
    def validate_json_format(cls, v):
        if v is None:
            return v

        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError as e:
                raise ValueError(f"DATAMIND_JSON_FORMAT 不是合法 JSON: {e}")

        if not isinstance(v, dict):
            raise ValueError("json_format 必须是 dict")

        result = {}
        for k, val in v.items():
            key = str(k)
            value = str(val)

            if not FIELD_PATTERN.match(key):
                raise ValueError(f"json_format key 不合法: {key}")

            if value not in VALID_LOGRECORD_FIELDS and not value.startswith("extra."):
                raise ValueError(f"json_format value 不合法: {value}")

            if value.startswith("extra.") and len(value.split(".")) != 2:
                raise ValueError(f"extra 字段格式错误: {value}")

            result[key] = value

        if not result:
            raise ValueError("json_format 不能为空")

        return result

    @field_validator('rotation_at_time')
    @classmethod
    def validate_rotation_at_time(cls, v):
        if v is not None:
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError("rotation_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('cleanup_at_time')
    @classmethod
    def validate_cleanup_at_time(cls, v):
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("cleanup_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('log_dir')
    @classmethod
    def validate_log_dir(cls, v):
        if not v or v.strip() == "":
            raise ValueError("log_dir 不能为空")
        if '../' in v or '..\\' in v:
            raise ValueError("log_dir 不能包含相对路径跳转")
        return v

    @field_validator('text_suffix', 'json_suffix')
    @classmethod
    def validate_suffix(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError(f"文件后缀只能包含字母、数字、下划线和连字符: {v}")
        return v

    @model_validator(mode='after')
    def validate_remote_config(self):
        if self.enable_remote and not self.remote_url:
            raise ValueError("启用远程日志时必须提供 remote_url")
        return self

    @model_validator(mode='after')
    def validate_rotation_strategy(self):
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
        if self.format in (LogFormat.JSON, LogFormat.BOTH):
            if self.json_timestamp_field not in self.json_format:
                raise ValueError(f"json_format 必须包含 {self.json_timestamp_field}")
        return self


# ==================== 全局配置实例 ====================

_logging_config: Optional[LoggingConfig] = None


def get_logging_config() -> LoggingConfig:
    """获取日志配置实例"""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig()
    return _logging_config


def reload_logging_config() -> LoggingConfig:
    """重新加载日志配置"""
    global _logging_config
    _logging_config = LoggingConfig()
    return _logging_config


__all__ = [
    "LoggingConfig",
    "get_logging_config",
    "reload_logging_config",
    "LogLevel",
    "LogFormat",
    "RotationWhen",
    "TimeZone",
    "TimestampPrecision",
    "EpochUnit",
    "RotationStrategy",
    "LogField",
    "SensitiveField",
]