import os
import logging
from pydantic import Field, field_validator
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

_bootstrap_logger = logging.getLogger("datamind.bootstrap")

BASE_DIR = Path(
    os.getenv(
        "DATAMIND_HOME",
        Path(__file__).resolve().parent.parent
    )
).resolve()

ENV_MAP = {
    "dev": ".env.dev",
    "development": ".env.dev",

    "test": ".env.test",
    "testing": ".env.test",

    "prod": ".env.prod",
    "production": ".env.prod",
}

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
    S = "S"  # 秒
    M = "M"  # 分钟
    H = "H"  # 小时
    D = "D"  # 天
    MIDNIGHT = "MIDNIGHT"  # 每天午夜
    W0 = "W0"  # 星期一
    W1 = "W1"  # 星期二
    W2 = "W2"  # 星期三
    W3 = "W3"  # 星期四
    W4 = "W4"  # 星期五
    W5 = "W5"  # 星期六
    W6 = "W6"  # 星期日


class TimeZone(str, Enum):
    """时区枚举"""
    UTC = "UTC"
    LOCAL = "LOCAL"
    CST = "CST"  # 中国标准时间
    EST = "EST"  # 美国东部时间
    PST = "PST"  # 美国太平洋时间


class TimestampPrecision(str, Enum):
    """时间戳精度"""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"

class LoggingConfig(BaseSettings):
    """
    完整的日志配置模型（包含时间格式）
    """

    _env: Optional[str] = PrivateAttr(default=None)
    _env_file: Optional[str] = PrivateAttr(default=None)
    _base_dir: Optional[Path] = PrivateAttr(default=None)
    _converting_format: bool = PrivateAttr(default=False)
    _format_cache: Dict[str, str] = PrivateAttr(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid"
    )

    # 基本配置
    name: str = Field(
        default="Datamind",
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

    # 时间格式配置
    timezone: TimeZone = Field(
        default=TimeZone.UTC,
        validation_alias="DATAMIND_LOG_TIMEZONE",
        description="日志时区"
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
        description="文本日志完整时间格式"
    )

    # JSON日志时间格式
    json_timestamp_field: str = Field(
        default="@timestamp",
        validation_alias="DATAMIND_JSON_TIMESTAMP_FIELD",
        description="JSON日志时间字段名"
    )
    json_date_format: str = Field(
        default="yyyy-MM-dd",
        validation_alias="DATAMIND_JSON_DATE_FORMAT",
        description="JSON日志日期格式"
    )
    json_datetime_format: str = Field(
        default="yyyy-MM-dd'T'HH:mm:ss.SSSZ",
        validation_alias="DATAMIND_JSON_DATETIME_FORMAT",
        description="JSON日志时间格式（ISO8601）"
    )
    json_use_epoch: bool = Field(
        default=False,
        validation_alias="DATAMIND_JSON_USE_EPOCH",
        description="JSON日志使用时间戳"
    )
    json_epoch_unit: str = Field(
        default="milliseconds",
        validation_alias="DATAMIND_JSON_EPOCH_UNIT",
        description="时间戳单位：seconds/milliseconds/microseconds/nanoseconds"
    )

    # 日志文件名时间格式
    file_name_timestamp: bool = Field(
        default=True,
        validation_alias="DATAMIND_FILE_NAME_TIMESTAMP",
        description="日志文件名是否包含时间戳"
    )
    file_name_date_format: str = Field(
        default="%Y%m%d",
        validation_alias="DATAMIND_FILE_NAME_DATE_FORMAT",
        description="日志文件名日期格式"
    )
    file_name_datetime_format: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_FILE_NAME_DATETIME_FORMAT",
        description="日志文件名完整时间格式"
    )

    # 文件轮转时间相关
    rotation_at_time: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_ROTATION_AT_TIME",
        description="定时轮转时间，如 '23:59'"
    )
    rotation_utc: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ROTATION_UTC",
        description="轮转时间是否使用UTC"
    )

    # 旧日志清理时间
    retention_days: int = Field(
        default=90,
        validation_alias="DATAMIND_LOG_RETENTION_DAYS",
        description="日志保留天数"
    )
    cleanup_at_time: str = Field(
        default="03:00",
        validation_alias="DATAMIND_LOG_CLEANUP_AT_TIME",
        description="日志清理时间"
    )

    # 时间偏移（用于日志同步）
    time_offset_hours: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_TIME_OFFSET_HOURS",
        description="日志时间偏移小时数"
    )

    # 文件配置
    file: str = Field(
        default="logs/Datamind.log",
        validation_alias="DATAMIND_LOG_FILE",
        description="日志文件路径"
    )
    error_file: Optional[str] = Field(
        default="logs/Datamind.error.log",
        validation_alias="DATAMIND_ERROR_LOG_FILE",
        description="错误日志单独文件"
    )

    # 日志格式
    format: LogFormat = Field(
        default=LogFormat.JSON,
        validation_alias="DATAMIND_LOG_FORMAT",
        description="日志格式：text/json/both"
    )
    text_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
        validation_alias="DATAMIND_TEXT_FORMAT",
        description="文本日志格式"
    )
    json_format: Dict[str, str] = Field(
        default_factory=lambda: {
            "@timestamp": "asctime",
            "level": "levelname",
            "logger": "name",
            "request_id": "request_id",
            "file": "filename",
            "line": "lineno",
            "function": "funcName",
            "message": "message",
            "exception": "exc_info"
        },
        validation_alias="DATAMIND_JSON_FORMAT",
        description="JSON日志格式"
    )

    # 文件轮转配置（按大小）
    max_bytes: int = Field(
        default=104857600,
        validation_alias="DATAMIND_LOG_MAX_BYTES",
        description="单个日志文件最大字节数"
    )
    backup_count: int = Field(
        default=30,
        validation_alias="DATAMIND_LOG_BACKUP_COUNT",
        description="备份文件数量"
    )

    # 时间轮转配置
    rotation_when: Optional[RotationWhen] = Field(
        default=RotationWhen.MIDNIGHT,
        validation_alias="DATAMIND_LOG_ROTATION_WHEN",
        description="日志轮转时间单位"
    )
    rotation_interval: int = Field(
        default=1,
        validation_alias="DATAMIND_LOG_ROTATION_INTERVAL",
        description="日志轮转间隔"
    )

    # 并发处理
    use_concurrent: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_USE_CONCURRENT",
        description="是否使用并发安全的日志处理器"
    )
    concurrent_lock_dir: str = Field(
        default="/tmp/datamind-logs",
        validation_alias="DATAMIND_LOG_LOCK_DIR",
        description="并发日志锁目录"
    )

    # 异步日志
    use_async: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ASYNC",
        description="是否使用异步日志"
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
        description="日志采样率 (0.0-1.0)"
    )
    sampling_interval: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_SAMPLING_INTERVAL",
        description="采样间隔（秒），0表示不限制"
    )

    # 敏感信息脱敏
    mask_sensitive: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_MASK_SENSITIVE",
        description="是否脱敏敏感信息"
    )
    sensitive_fields: List[str] = Field(
        default_factory=lambda: ["id_number", "phone", "card_number", "password", "token"],
        validation_alias="DATAMIND_SENSITIVE_FIELDS",
        description="需要脱敏的字段"
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
        description="是否记录访问日志"
    )
    access_log_file: str = Field(
        default="logs/access.log",
        validation_alias="DATAMIND_ACCESS_LOG_FILE",
        description="访问日志文件"
    )

    enable_audit_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_AUDIT",
        description="是否记录审计日志"
    )
    audit_log_file: str = Field(
        default="logs/audit.log",
        validation_alias="DATAMIND_AUDIT_LOG_FILE",
        description="审计日志文件"
    )

    enable_performance_log: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_PERFORMANCE",
        description="是否记录性能日志"
    )
    performance_log_file: str = Field(
        default="logs/performance.log",
        validation_alias="DATAMIND_PERFORMANCE_LOG_FILE",
        description="性能日志文件"
    )

    # 日志过滤
    filters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_paths": ["/health", "/metrics"],
            "exclude_status_codes": [404],
            "min_duration_ms": 0
        },
        validation_alias="DATAMIND_LOG_FILTERS",
        description="日志过滤器"
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
        description="远程日志批量发送大小"
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
        description="控制台输出级别"
    )

    # 归档配置
    archive_enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ARCHIVE",
        description="是否启用日志归档"
    )
    archive_path: str = Field(
        default="/data/logs/archive",
        validation_alias="DATAMIND_LOG_ARCHIVE_PATH",
        description="日志归档路径"
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

    @field_validator('sampling_rate')
    def validate_sampling_rate(cls, v):
        if v < 0 or v > 1:
            raise ValueError("采样率必须在0到1之间")
        return v

    @field_validator('max_bytes')
    def validate_max_bytes(cls, v):
        if v < 1024:
            raise ValueError("max_bytes 不能小于1KB")
        return v

    def get_python_date_format(self) -> str:
        """获取Python日期格式"""
        if self.format == LogFormat.JSON:
            return self._convert_to_python_format(self.json_datetime_format)
        else:
            return self.text_datetime_format

    def _convert_to_python_format(self, java_format: str) -> str:
        """
        将Java日期格式转换为Python格式

        使用排序确保长模式优先匹配，避免冲突

        示例：
            yyyy-MM-dd'T'HH:mm:ss.SSSZ -> %Y-%m-%d'T'%H:%M:%S.%f%z
            yy-MM-dd -> %y-%m-%d
            HH:mm:ss.SSS -> %H:%M:%S.%f
        """

        # 检查缓存
        if java_format in self._format_cache:
            return self._format_cache[java_format]

        # 如果已经在转换中，直接返回，防止递归
        if getattr(self, '_converting_format', False):
            return java_format

        self._converting_format = True
        try:
            mapping = {
                'yyyy': '%Y',
                'yy': '%y',
                'MM': '%m',
                'dd': '%d',
                'HH': '%H',
                'mm': '%M',
                'ss': '%S',
                'SSS': '%f',
                'XXX': '%z',
                'Z': '%z',
                'T': 'T',
            }

            sorted_patterns = sorted(mapping.keys(), key=len, reverse=True)
            python_format = java_format
            original = java_format

            for pattern in sorted_patterns:
                replacement = mapping[pattern]
                python_format = python_format.replace(pattern, replacement)

            # 存入缓存
            self._format_cache[java_format] = python_format

            # 只在非递归调用时记录日志
            # 可以加个条件避免首次转换时也触发日志（如果缓存后不再需要日志）
            if original != python_format:
                _bootstrap_logger.debug("日期格式转换: %s -> %s", original, python_format)

            return python_format
        finally:
            self._converting_format = False

    @classmethod
    def load(
            cls,
            env: Optional[str] = None,
            env_file: Optional[str] = None,
            base_dir: Optional[Path] = None
    ):
        """
        自动加载配置

        环境变量优先级（低 → 高）：

        1. .env
        2. .env.{env}          (如 .env.dev / .env.test / .env.prod)
        3. .env.local          (本地覆盖)
        4. env_file 参数       (最高优先级)
        """

        base_dir = (base_dir or BASE_DIR).resolve()

        env = (
            env
            or os.getenv("ENVIRONMENT")
            or os.getenv("ENV")
            or "production"
        ).lower()

        env_files: List[Path] = []

        default_env = base_dir / ".env"
        if default_env.exists():
            env_files.append(default_env)

        env_name = ENV_MAP.get(env)
        if env_name:
            env_path = base_dir / env_name
            if env_path.exists():
                env_files.append(env_path)

        local_env = base_dir / ".env.local"
        if local_env.exists():
            env_files.append(local_env)

        # 加载默认 env 文件
        env_files = list(dict.fromkeys(env_files))
        if env_files:
            _bootstrap_logger.info("加载环境变量文件: %s", [str(p) for p in env_files])

            for file in env_files:
                load_dotenv(file, override=True)

        # env_file 参数（最高优先级）
        if env_file:
            _bootstrap_logger.info("使用环境变量文件: %s", env_file)
            load_dotenv(env_file, override=True, verbose=False)

        config = cls()

        config._env = env
        config._env_file = env_file
        config._base_dir = base_dir

        config.ensure_log_dirs(base_dir)

        return config

    def reload(self):
        """重新加载配置"""
        return self.load(
            env=self._env,
            env_file=self._env_file,
            base_dir=self._base_dir
        )

    def ensure_log_dirs(self, base_dir: Optional[Path] = None):

        base_dir = (base_dir or BASE_DIR).resolve()

        paths = [
            self.file,
            self.error_file,
            self.access_log_file,
            self.audit_log_file,
            self.performance_log_file,
        ]

        for path in paths:
            if not path:
                continue

            log_path = Path(path)

            if not log_path.is_absolute():
                log_path = base_dir / log_path

            log_dir = log_path.parent

            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
                _bootstrap_logger.info("创建日志目录: %s", log_dir)