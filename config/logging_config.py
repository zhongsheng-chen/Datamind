# datamind/config/logging_config.py

import re
import json
import logging
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(int, Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG  # 10
    INFO = logging.INFO  # 20
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR  # 40
    CRITICAL = logging.CRITICAL  # 50


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


# 验证用的常量
VALID_LOGRECORD_FIELDS = {
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module',
    'msecs', 'msg', 'name', 'pathname', 'process', 'processName',
    'relativeCreated', 'stack_info', 'thread', 'threadName'
}

FIELD_PATTERN = re.compile(r"^[a-zA-Z0-9_.@\-\[\]]+$")


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
        default="@timestamp",
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
        default="milliseconds",
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
            "@timestamp": "asctime",
            "log.level": "levelname",
            "log.logger": "name",
            "message": "message",
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
        default_factory=lambda: {
            "id_number", "phone", "card_number", "password", "token"
        },
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

    @field_validator('level', 'console_level', mode='before')
    @classmethod
    def coerce_log_level(cls, v):
        """将字符串或整数转换为 LogLevel 枚举"""
        # 如果已经是 LogLevel 枚举，直接返回
        if isinstance(v, LogLevel):
            return v

        # 如果是整数，尝试转换为对应的枚举
        if isinstance(v, int):
            try:
                return LogLevel(v)
            except ValueError:
                # 如果整数不在枚举范围内，返回默认值
                return LogLevel.INFO

        # 如果是字符串，转换为对应的枚举
        if isinstance(v, str):
            level_map = {
                "DEBUG": LogLevel.DEBUG,
                "INFO": LogLevel.INFO,
                "WARNING": LogLevel.WARNING,
                "ERROR": LogLevel.ERROR,
                "CRITICAL": LogLevel.CRITICAL,
            }
            # 忽略大小写
            return level_map.get(v.upper(), LogLevel.INFO)

        # 其他情况返回默认值
        return LogLevel.INFO

    @field_validator('sampling_rate')
    @classmethod
    def validate_sampling_rate(cls, v):
        """验证采样率"""
        if v < 0 or v > 1:
            raise ValueError("采样率必须在0到1之间")
        return v

    @field_validator('max_bytes')
    @classmethod
    def validate_max_bytes(cls, v):
        """验证最大字节数"""
        if v < 0:
            raise ValueError("max_bytes 不能为负数")
        return v

    @field_validator("json_format", mode="before")
    @classmethod
    def validate_json_format(cls, v):
        """验证JSON格式配置"""
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
        """验证轮转时间格式"""
        if v is not None:
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError("rotation_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('cleanup_at_time')
    @classmethod
    def validate_cleanup_at_time(cls, v):
        """验证清理时间格式"""
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("cleanup_at_time 必须是 HH:MM 格式")
        return v

    @field_validator('log_dir')
    @classmethod
    def validate_log_dir(cls, v):
        """验证日志目录"""
        if v and ('../' in v or '..\\' in v):
            raise ValueError("log_dir 不能包含相对路径跳转")
        return v

    @model_validator(mode='after')
    def validate_remote_config(self):
        """验证远程日志配置"""
        if self.enable_remote and not self.remote_url:
            raise ValueError("启用远程日志时必须提供 remote_url")
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
        """验证JSON日志时间戳配置"""
        if self.format in (LogFormat.JSON, LogFormat.BOTH):
            if self.json_timestamp_field not in self.json_format:
                raise ValueError(f"json_format 必须包含 {self.json_timestamp_field}")
        return self


__all__ = [
    "LoggingConfig",
    "LogLevel",
    "LogFormat",
    "RotationWhen",
    "TimeZone",
    "TimestampPrecision",
    "EpochUnit",
    "RotationStrategy"
]