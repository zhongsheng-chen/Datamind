# config/logging_config.py

import os
import re
import json
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime
from pydantic import Field, field_validator, model_validator
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any, Union, Set

BASE_DIR = Path(
    os.getenv(
        "DATAMIND_HOME",
        Path(__file__).resolve().parent.parent
    )
).resolve()

VALID_LOGRECORD_FIELDS = set(vars(logging.makeLogRecord({})).keys()) | {
    "message",
    "asctime",
}

FIELD_PATTERN = re.compile(r"^[a-zA-Z0-9_.@\-\[\]]+$")


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class RotationStrategy(str, Enum):
    SIZE = "size"
    TIME = "time"


class LoggingConfig(BaseSettings):
    """日志配置"""

    _env: Optional[str] = PrivateAttr(default=None)
    _base_dir: Optional[Path] = PrivateAttr(default=None)
    _last_modified: Optional[datetime] = PrivateAttr(default=None)
    _converting_format: bool = PrivateAttr(default=False)
    _format_cache: Dict[str, str] = PrivateAttr(default_factory=dict)
    _config_digest: Optional[str] = PrivateAttr(default=None)

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
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
    formatter_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FORMATTER_DEBUG"
    )
    manager_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_MANAGER_DEBUG"
    )
    handler_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_HANDLER_DEBUG"
    )
    filter_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FILTER_DEBUG"
    )
    context_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CONTEXT_DEBUG"
    )
    cleanup_debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CLEANUP_DEBUG"
    )

    # 时间格式配置
    timezone: TimeZone = Field(
        default=TimeZone.UTC,
        validation_alias="DATAMIND_LOG_TIMEZONE"
    )
    timestamp_precision: TimestampPrecision = Field(
        default=TimestampPrecision.MILLISECONDS,
        validation_alias="DATAMIND_LOG_TIMESTAMP_PRECISION"
    )

    # 文本日志时间格式
    text_date_format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        validation_alias="DATAMIND_TEXT_DATE_FORMAT"
    )
    text_datetime_format: str = Field(
        default="%Y-%m-%d %H:%M:%S.%f",
        validation_alias="DATAMIND_TEXT_DATETIME_FORMAT"
    )

    # JSON日志时间格式
    json_timestamp_field: str = Field(
        default="@timestamp",
        validation_alias="DATAMIND_JSON_TIMESTAMP_FIELD"
    )
    json_date_format: str = Field(
        default="yyyy-MM-dd",
        validation_alias="DATAMIND_JSON_DATE_FORMAT"
    )
    json_datetime_format: str = Field(
        default="yyyy-MM-dd'T'HH:mm:ss.SSSZ",
        validation_alias="DATAMIND_JSON_DATETIME_FORMAT"
    )
    json_use_epoch: bool = Field(
        default=False,
        validation_alias="DATAMIND_JSON_USE_EPOCH"
    )
    json_epoch_unit: EpochUnit = Field(
        default="milliseconds",
        validation_alias="DATAMIND_JSON_EPOCH_UNIT"
    )

    # 日志文件名时间格式
    file_name_timestamp: bool = Field(
        default=True,
        validation_alias="DATAMIND_FILE_NAME_TIMESTAMP"
    )
    file_name_date_format: str = Field(
        default="%Y%m%d",
        validation_alias="DATAMIND_FILE_NAME_DATE_FORMAT"
    )
    file_name_datetime_format: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_FILE_NAME_DATETIME_FORMAT"
    )

    # 文件轮转时间相关
    rotation_at_time: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_ROTATION_AT_TIME"
    )
    rotation_utc: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ROTATION_UTC"
    )

    # 旧日志清理时间
    retention_days: int = Field(
        default=90,
        validation_alias="DATAMIND_LOG_RETENTION_DAYS"
    )
    cleanup_at_time: str = Field(
        default="03:00",
        validation_alias="DATAMIND_LOG_CLEANUP_AT_TIME"
    )

    # 时间偏移
    time_offset_hours: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_TIME_OFFSET_HOURS"
    )

    # 日志目录配置
    log_dir: str = Field(
        default="logs",
        validation_alias="DATAMIND_LOG_DIR"
    )

    # 文件配置
    file: str = Field(
        default="datamind.log",
        validation_alias="DATAMIND_LOG_FILE"
    )
    error_file: Optional[str] = Field(
        default="datamind.error.log",
        validation_alias="DATAMIND_ERROR_LOG_FILE"
    )

    # 日志格式
    format: LogFormat = Field(
        default=LogFormat.JSON,
        validation_alias="DATAMIND_LOG_FORMAT"
    )
    text_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
        validation_alias="DATAMIND_TEXT_FORMAT"
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
            "source.function": "funcName",
            "process.pid": "process",
            "process.thread": "threadName",
            "error.stack": "exc_info"
        },
        validation_alias="DATAMIND_JSON_FORMAT"
    )

    # 日志文件后缀
    text_suffix: str = Field(
        default="text",
        validation_alias="DATAMIND_TEXT_SUFFIX"
    )
    json_suffix: str = Field(
        default="json",
        validation_alias="DATAMIND_JSON_SUFFIX"
    )

    # 文件轮转配置（按大小）
    max_bytes: int = Field(
        default=104857600,
        validation_alias="DATAMIND_LOG_MAX_BYTES"
    )
    backup_count: int = Field(
        default=30,
        validation_alias="DATAMIND_LOG_BACKUP_COUNT"
    )

    # 时间轮转配置
    rotation_strategy: RotationStrategy = Field(
        default=RotationStrategy.TIME,
        validation_alias="DATAMIND_LOG_ROTATION_STRATEGY"
    )
    rotation_when: Optional[RotationWhen] = Field(
        default=RotationWhen.MIDNIGHT,
        validation_alias="DATAMIND_LOG_ROTATION_WHEN"
    )
    rotation_interval: int = Field(
        default=1,
        validation_alias="DATAMIND_LOG_ROTATION_INTERVAL"
    )

    # 并发处理
    use_concurrent: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_USE_CONCURRENT"
    )
    concurrent_lock_dir: str = Field(
        default="/tmp/datamind-logs",
        validation_alias="DATAMIND_LOG_LOCK_DIR"
    )

    # 异步日志
    use_async: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ASYNC"
    )
    async_queue_size: int = Field(
        default=10000,
        validation_alias="DATAMIND_LOG_QUEUE_SIZE"
    )

    # 日志采样
    sampling_rate: float = Field(
        default=1.0,
        validation_alias="DATAMIND_LOG_SAMPLING_RATE"
    )
    sampling_interval: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_SAMPLING_INTERVAL"
    )

    # 敏感信息脱敏
    mask_sensitive: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_MASK_SENSITIVE"
    )
    sensitive_fields: Set[str] = Field(
        default_factory=lambda: {
            "id_number",
            "phone",
            "card_number",
            "password",
            "token"
        },
        validation_alias="DATAMIND_SENSITIVE_FIELDS"
    )
    mask_char: str = Field(
        default="*",
        validation_alias="DATAMIND_LOG_MASK_CHAR"
    )

    # 日志分类
    enable_access_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ACCESS"
    )
    access_log_file: str = Field(
        default="datamind.access.log",
        validation_alias="DATAMIND_ACCESS_LOG_FILE"
    )

    enable_audit_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_AUDIT"
    )
    audit_log_file: str = Field(
        default="datamind.audit.log",
        validation_alias="DATAMIND_AUDIT_LOG_FILE"
    )

    enable_performance_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_PERFORMANCE"
    )
    performance_log_file: str = Field(
        default="datamind.performance.log",
        validation_alias="DATAMIND_PERFORMANCE_LOG_FILE"
    )

    # 日志过滤
    filters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_paths": ["/health", "/metrics"],
            "exclude_status_codes": [404],
            "min_duration_ms": 0
        },
        validation_alias="DATAMIND_LOG_FILTERS"
    )

    # 远程日志
    enable_remote: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_REMOTE"
    )
    remote_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_URL"
    )
    remote_token: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_TOKEN"
    )
    remote_timeout: int = Field(
        default=5,
        validation_alias="DATAMIND_LOG_REMOTE_TIMEOUT"
    )
    remote_batch_size: int = Field(
        default=100,
        validation_alias="DATAMIND_LOG_REMOTE_BATCH_SIZE"
    )

    # 控制台输出
    console_output: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_CONSOLE"
    )
    console_level: LogLevel = Field(
        default=LogLevel.INFO,
        validation_alias="DATAMIND_LOG_CONSOLE_LEVEL"
    )

    # 归档配置
    archive_enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ARCHIVE"
    )
    archive_path: str = Field(
        default="archive",
        validation_alias="DATAMIND_LOG_ARCHIVE_PATH"
    )
    archive_compression: str = Field(
        default="gz",
        validation_alias="DATAMIND_LOG_COMPRESSION"
    )
    archive_name_format: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_ARCHIVE_NAME_FORMAT"
    )

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

        result: Dict[str, str] = {}

        for k, val in v.items():

            key = str(k)
            value = str(val)

            if not FIELD_PATTERN.match(key):
                raise ValueError(f"json_format key 不合法: {key}")

            if value not in VALID_LOGRECORD_FIELDS and not value.startswith("extra."):
                raise ValueError(f"json_format value 不合法: {value}")

            if value.startswith("extra.") and len(value.split(".")) != 2:
                raise ValueError(
                    f"extra 字段格式错误: {value}"
                )

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

    @model_validator(mode='after')
    def validate_remote_config(self):
        if self.enable_remote and not self.remote_url:
            raise ValueError("启用远程日志时必须提供 remote_url")
        return self

    @field_validator('log_dir')
    @classmethod
    def validate_log_dir(cls, v):
        if v and ('../' in v or '..\\' in v):
            raise ValueError("log_dir 不能包含相对路径跳转")
        return v

    @model_validator(mode="after")
    def run_full_validation(self):

        report = self.validate_all()

        if not report["valid"]:
            raise ValueError(report["errors"])

        return self

    @model_validator(mode="after")
    def validate_json_timestamp(self):

        if self.format in (LogFormat.JSON, LogFormat.BOTH):

            if self.json_timestamp_field not in self.json_format:
                raise ValueError(
                    f"json_format 必须包含 {self.json_timestamp_field}"
                )

        return self

    def _convert_to_python_format(self, java_format: str) -> str:
        """将Java日期格式转换为Python格式"""

        if java_format in self._format_cache:
            return self._format_cache[java_format]

        if getattr(self, "_converting_format", False):
            return java_format

        self._converting_format = True

        try:
            mapping = {
                "yyyy": "%Y",
                "yy": "%y",
                "MM": "%m",
                "dd": "%d",
                "HH": "%H",
                "mm": "%M",
                "ss": "%S",
                "SSS": "{millis}",
                "XXX": "%z",
                "Z": "%z",
                "T": "T",
            }

            sorted_patterns = sorted(mapping.keys(), key=len, reverse=True)

            python_format = java_format

            for pattern in sorted_patterns:
                python_format = python_format.replace(pattern, mapping[pattern])

            self._format_cache[java_format] = python_format
            return python_format

        finally:
            self._converting_format = False

    def _get_log_dir_path(self) -> Path:
        """获取日志目录路径"""
        base_dir = self._base_dir or BASE_DIR
        log_dir_path = Path(self.log_dir)
        if not log_dir_path.is_absolute():
            log_dir_path = base_dir / self.log_dir
        return log_dir_path

    def get_python_date_format(self) -> str:
        """获取Python日期格式"""
        if self.format == LogFormat.JSON:
            return self._convert_to_python_format(self.json_datetime_format)
        return self.text_datetime_format

    def get_formatted_timestamp(self, dt: Optional[datetime] = None) -> Union[str, float]:
        """统一的 timestamp 格式化方法"""
        from core.logging import TimezoneFormatter
        return TimezoneFormatter(self).format_timestamp(dt)

    def get_config_digest(self) -> str:
        """获取配置摘要"""
        import hashlib
        import json

        if self._config_digest:
            return self._config_digest

        config_str = self.model_dump_json(
            exclude={
                '_env', '_base_dir', '_last_modified',
                '_converting_format', '_format_cache'
            },
            sort_keys=True
        )
        self._config_digest = hashlib.md5(config_str.encode()).hexdigest()
        return self._config_digest

    def get_handler_config(
            self,
            handler_class,
            filename: str
    ) -> Dict[str, Any]:
        """
        获取 handler 配置

        Args:
            handler_class: handler 类型
            filename: 日志文件名

        Returns:
            {
                "class": HandlerClass,
                "kwargs": {...}
            }
        """

        log_path = str(self.get_full_log_path(filename))

        kwargs = {
            "filename": log_path,
            "encoding": self.encoding,
        }

        handler_name = handler_class.__name__

        if handler_name == "TimedRotatingFileHandler":

            kwargs.update(
                when=self.rotation_when.value,
                interval=self.rotation_interval,
                backupCount=self.backup_count,
                utc=self.rotation_utc
            )

        elif handler_name == "RotatingFileHandler":

            kwargs.update(
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )

        return {
            "class": handler_class,
            "kwargs": kwargs
        }

    def get_full_log_path(self, relative_path: str) -> Path:
        """获取完整的日志文件路径"""
        base_dir = self._base_dir or BASE_DIR
        log_dir_path = Path(self.log_dir)
        if log_dir_path.is_absolute():
            return log_dir_path / relative_path
        return base_dir / self.log_dir / relative_path

    def get_all_log_paths(self) -> Dict[str, Path]:
        """获取所有日志文件的完整路径"""
        paths = {}
        log_files = {
            'main': self.file,
            'error': self.error_file,
            'access': self.access_log_file,
            'audit': self.audit_log_file,
            'performance': self.performance_log_file,
        }
        for key, rel_path in log_files.items():
            if rel_path:
                paths[key] = self.get_full_log_path(rel_path)
        if self.archive_enabled:
            paths['archive'] = self.get_full_log_path(self.archive_path)
        return paths

    def get_default_suffix(self) -> str:
        """根据日志格式返回默认后缀"""

        if self.format == LogFormat.JSON:
            return self.json_suffix

        if self.format == LogFormat.TEXT:
            return self.text_suffix

        return "log"

    def get_log_file_name(
            self,
            name: str,
            suffix: Optional[str] = None,
            with_timestamp: bool = False
    ) -> str:
        """
        生成日志文件名

        Args:
            name: 日志名称 (datamind.log / datamind.error.log)
            suffix: 文件后缀 (json / text / log)
            with_timestamp: 是否添加时间戳

        Returns:
            str
        """

        path = Path(name)

        stem = path.stem

        # suffix 优先级
        if suffix:
            ext = f".{suffix.lstrip('.')}"
        elif path.suffix:
            ext = path.suffix
        else:
            ext = f".{self.get_default_suffix()}"

        # 时间戳
        if with_timestamp and self.file_name_timestamp:
            ts = datetime.now().strftime(
                self.file_name_date_format
            )

            stem = f"{stem}.{ts}"

        return f"{stem}{ext}"

    def get_all_log_file_names(self) -> Dict[str, str]:
        """
        获取所有日志文件名

        Returns:
            {
                "main": "...",
                "error": "...",
                "access": "...",
                "audit": "...",
                "performance": "..."
            }
        """

        result = {}

        if self.file:
            result["main"] = self.get_log_file_name(self.file)

        if self.error_file:
            result["error"] = self.get_log_file_name(self.error_file)

        if self.enable_access_log:
            result["access"] = self.get_log_file_name(self.access_log_file)

        if self.enable_audit_log:
            result["audit"] = self.get_log_file_name(self.audit_log_file)

        if self.enable_performance_log:
            result["performance"] = self.get_log_file_name(self.performance_log_file)

        return result

    def ensure_directories(self) -> Dict[str, bool]:
        """确保所有日志目录存在"""
        result: Dict[str, bool] = {}

        def ensure_dir(path: Path):
            try:
                before = path.exists()
                path.mkdir(parents=True, exist_ok=True)

                if not before:
                    result[str(path)] = True

                if not os.access(path, os.W_OK):
                    raise PermissionError(f"目录不可写: {path}")

            except PermissionError:
                raise PermissionError(f"没有权限创建或写入目录: {path}")
            except Exception as e:
                raise RuntimeError(f"创建目录失败: {path} ({e})")

        # 主日志目录
        log_dir_path = self._get_log_dir_path()
        ensure_dir(log_dir_path)

        # 其他日志文件目录
        for path in self.get_all_log_paths().values():
            target_dir = path.parent
            if target_dir != log_dir_path:
                ensure_dir(target_dir)

        # 并发锁目录
        if self.use_concurrent:
            lock_dir = Path(self.concurrent_lock_dir)
            if not lock_dir.is_absolute():
                lock_dir = (self._base_dir or BASE_DIR) / lock_dir
            ensure_dir(lock_dir)

        return result

    def to_logging_level(self, level: Union['LogLevel', int, str, None] = None) -> int:
        """转换为 logging 模块的级别"""
        if level is None:
            level = self.level
        if isinstance(level, LogLevel):
            return getattr(logging, level.value)
        if isinstance(level, int):
            return level
        if isinstance(level, str):
            return getattr(logging, level.upper())
        return logging.INFO

    def to_dict(self, exclude_sensitive: bool = True) -> Dict[str, Any]:
        """导出配置为字典"""
        data = self.model_dump()
        if exclude_sensitive and 'remote_token' in data:
            data.pop('remote_token')
        return data

    def validate_all(self) -> Dict[str, Any]:
        """
        全面验证配置，返回验证报告

        Returns:
            验证报告，包含：
            - valid: 配置是否有效
            - errors: 错误列表（致命问题）
            - warnings: 警告列表（建议性问题）
            - info: 信息列表（配置摘要）
        """
        report = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {
                'name': self.name,
                'level': self.level.value,
                'format': self.format.value,
                'timezone': self.timezone.value,
                'log_dir': self.log_dir,
                'config_digest': self.get_config_digest()[:8]
            }
        }

        # 检查日志目录权限
        try:
            log_dir_path = self._get_log_dir_path()
            if log_dir_path.exists():
                if not os.access(log_dir_path, os.W_OK):
                    report['errors'].append(f"日志目录不可写: {log_dir_path}")
                    report['valid'] = False
            else:
                # 尝试创建目录来测试权限
                try:
                    log_dir_path.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    report['errors'].append(f"无法创建日志目录: {log_dir_path}")
                    report['valid'] = False
        except Exception as e:
            report['errors'].append(f"检查日志目录权限失败: {e}")
            report['valid'] = False

        # 检查远程日志配置
        if self.enable_remote:
            if not self.remote_url:
                report['errors'].append("启用远程日志时必须提供 remote_url")
                report['valid'] = False
            elif not (self.remote_url.startswith('http://') or self.remote_url.startswith('https://')):
                report['warnings'].append(f"remote_url 可能不是有效的URL: {self.remote_url}")

        # 检查归档配置
        if self.archive_enabled:
            try:
                archive_dir = self.get_full_log_path(self.archive_path).parent
                if archive_dir.exists():
                    if not os.access(archive_dir, os.W_OK):
                        report['errors'].append(f"归档目录不可写: {archive_dir}")
                        report['valid'] = False
            except Exception as e:
                report['errors'].append(f"检查归档目录失败: {e}")
                report['valid'] = False

        # 检查并发锁目录
        if self.use_concurrent:
            lock_dir = Path(self.concurrent_lock_dir)
            if not lock_dir.is_absolute():
                lock_dir = (self._base_dir or BASE_DIR) / lock_dir
            if lock_dir.exists():
                if not os.access(lock_dir, os.W_OK):
                    report['errors'].append(f"并发锁目录不可写: {lock_dir}")
                    report['valid'] = False

        # 检查必要的文件路径
        if not self.file:
            report['errors'].append("file 不能为空")
            report['valid'] = False

        # 检查编码是否有效
        try:
            'test'.encode(self.encoding)
        except LookupError:
            report['errors'].append(f"不支持的编码格式: {self.encoding}")
            report['valid'] = False

        # 如果已有致命错误，跳过后续检查
        if not report['valid']:
            return report

        # 采样配置警告
        if self.sampling_rate < 1.0:
            if self.sampling_interval > 0:
                report['warnings'].append(
                    "同时设置了 sampling_rate 和 sampling_interval，"
                    "可能导致日志采样不符合预期"
                )
            elif self.sampling_rate < 0.1:
                report['warnings'].append(
                    f"采样率设置过低 ({self.sampling_rate})，"
                    "可能导致重要日志丢失"
                )

        # 文件大小警告
        if self.max_bytes < 1024 * 1024:  # 小于1MB
            report['warnings'].append(
                f"max_bytes 设置过小 ({self.max_bytes} < 1MB)，"
                "可能导致频繁的文件轮转"
            )
        elif self.max_bytes > 1024 * 1024 * 1024:  # 大于1GB
            report['warnings'].append(
                f"max_bytes 设置过大 ({self.max_bytes} > 1GB)，"
                "可能导致单个日志文件过大"
            )

        # 备份数量警告
        if self.backup_count > 100:
            report['warnings'].append(
                f"backup_count 设置过大 ({self.backup_count} > 100)，"
                "可能占用过多磁盘空间"
            )
        elif self.backup_count < 2:
            report['warnings'].append(
                f"backup_count 设置过小 ({self.backup_count} < 2)，"
                "日志轮转可能无法保留足够的历史"
            )

        # 保留天数警告
        if self.retention_days < 7:
            report['warnings'].append(
                f"retention_days 设置过小 ({self.retention_days} < 7天)，"
                "日志可能过早被清理"
            )
        elif self.retention_days > 365:
            report['warnings'].append(
                f"retention_days 设置过大 ({self.retention_days} > 365天)，"
                "可能占用过多磁盘空间"
            )

        # 异步队列大小警告
        if self.use_async and self.async_queue_size < 100:
            report['warnings'].append(
                f"异步队列大小设置过小 ({self.async_queue_size} < 100)，"
                "可能导致日志丢失"
            )

        # 远程日志配置警告
        if self.enable_remote:
            if self.remote_timeout < 1:
                report['warnings'].append(
                    f"remote_timeout 设置过小 ({self.remote_timeout} < 1秒)，"
                    "可能导致远程日志频繁超时"
                )
            if self.remote_batch_size < 1:
                report['warnings'].append(
                    f"remote_batch_size 设置过小 ({self.remote_batch_size} < 1)，"
                    "可能导致远程日志发送效率低下"
                )

        # 检查文件名时间戳格式
        if self.file_name_timestamp:
            try:
                datetime.now().strftime(self.file_name_date_format)
                datetime.now().strftime(self.file_name_datetime_format)
            except ValueError as e:
                report['warnings'].append(f"文件名时间戳格式无效: {e}")

        # 检查清理时间格式
        try:
            datetime.strptime(self.cleanup_at_time, "%H:%M")
        except ValueError:
            report['warnings'].append(f"清理时间格式无效: {self.cleanup_at_time}，应为 HH:MM")

        # 检查敏感字段配置
        if self.mask_sensitive and not self.sensitive_fields:
            report['warnings'].append("启用了敏感信息脱敏，但未配置敏感字段")
        elif self.mask_sensitive and len(self.sensitive_fields) > 50:
            report['warnings'].append(f"敏感字段列表过长 ({len(self.sensitive_fields)} 个)")

        # 检查日志文件路径
        if self.error_file and self.error_file == self.file:
            report['warnings'].append("error_file 与 file 相同，错误日志不会单独存储")

        # 检查轮转策略
        if self.rotation_strategy == RotationStrategy.TIME:

            if not self.rotation_when:
                report['errors'].append(
                    "rotation_strategy=TIME 必须配置 rotation_when"
                )
                report['valid'] = False

            if self.rotation_interval < 1:
                report['errors'].append(
                    "rotation_interval 必须 >= 1"
                )
                report['valid'] = False

        elif self.rotation_strategy == RotationStrategy.SIZE:

            if self.max_bytes <= 0:
                report['errors'].append(
                    "rotation_strategy=SIZE 必须配置 max_bytes"
                )
                report['valid'] = False

        # 检查轮转配置
        if self.rotation_when and self.rotation_interval < 1:
            report['warnings'].append(f"rotation_interval 设置无效: {self.rotation_interval}")

        return report