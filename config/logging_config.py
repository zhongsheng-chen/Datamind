# config/logging_config.py
import os
import logging
from datetime import datetime
from pydantic import Field, field_validator, model_validator
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any, Union
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

    # 日志文件后缀
    text_suffix: str = Field(
        default="text",
        validation_alias="DATAMIND_TEXT_SUFFIX",
        description="文本日志文件后缀"
    )
    json_suffix: str = Field(
        default="json",
        validation_alias="DATAMIND_JSON_SUFFIX",
        description="JSON日志文件后缀"
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

    @field_validator('json_epoch_unit')
    def validate_json_epoch_unit(cls, v):
        valid_units = ['seconds', 'milliseconds', 'microseconds', 'nanoseconds']
        if v not in valid_units:
            raise ValueError(f"json_epoch_unit 必须是 {valid_units} 之一")
        return v

    @field_validator('rotation_at_time')
    def validate_rotation_at_time(cls, v):
        if v is not None:
            import re
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError("rotation_at_time 必须是 HH:MM 格式，如 '23:59'")
        return v

    @model_validator(mode='after')
    def validate_remote_config(self):
        """验证远程日志配置"""
        if self.enable_remote and not self.remote_url:
            raise ValueError("启用远程日志时必须提供 remote_url")
        return self

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

    def get_log_manager(self):
        from core.log_manager import log_manager
        return log_manager

    def get_python_date_format(self) -> str:
        """获取Python日期格式"""
        if self.format == LogFormat.JSON:
            return self._convert_to_python_format(self.json_datetime_format)
        else:
            return self.text_datetime_format

    def get_formatted_timestamp(self, dt: Optional[datetime] = None) -> Union[str, float]:
        """统一的 timestamp 格式化方法"""
        from core.log_manager import TimezoneFormatter
        formatter = TimezoneFormatter(self)
        return formatter.format_timestamp(dt)

    def get_env_files(self) -> List[str]:
        """获取当前配置使用的环境文件列表"""
        env_files = []

        if self._env_file:
            env_files.append(self._env_file)

        base_dir = self._base_dir or BASE_DIR
        for env_name in ['.env', f'.env.{self._env}', '.env.local']:
            env_path = base_dir / env_name
            if env_path.exists():
                env_files.append(str(env_path))

        return env_files

    def get_config_digest(self) -> str:
        """获取配置摘要，用于判断配置是否变化"""
        import hashlib
        import json

        # 排除私有属性和运行时状态
        config_dict = self.model_dump(exclude={
            '_env', '_env_file', '_base_dir', '_converting_format', '_format_cache'
        })

        # 排序以确保一致性
        config_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def ensure_log_dirs(self, base_dir: Optional[Path] = None) -> Dict[str, bool]:
        """
        确保所有日志目录存在

        Returns:
            目录创建状态字典 {path: created}
        """
        base_dir = (base_dir or BASE_DIR).resolve()
        results = {}

        # 收集所有需要检查的路径
        paths_to_check = [
            self.file,
            self.error_file,
            self.access_log_file,
            self.audit_log_file,
            self.performance_log_file,
        ]

        # 添加归档路径
        if self.archive_enabled:
            paths_to_check.append(self.archive_path)

        # 添加并发锁目录
        if self.use_concurrent:
            paths_to_check.append(self.concurrent_lock_dir)

        for path in paths_to_check:
            if not path:
                continue

            log_path = Path(path)
            if not log_path.is_absolute():
                log_path = base_dir / log_path

            # 如果是文件，取父目录；如果是目录，直接使用
            if log_path.suffix:  # 有后缀，说明是文件
                target_dir = log_path.parent
            else:
                target_dir = log_path

            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                results[str(target_dir)] = True
                _bootstrap_logger.info("创建日志目录: %s", target_dir)
            else:
                results[str(target_dir)] = False

        return results

    def to_logging_level(self, level: Union['LogLevel', int, str, None] = None) -> int:
        """转换为 logging 模块的级别"""
        if level is None:
            level = self.level

        if isinstance(level, LogLevel):
            return getattr(logging, level.value)
        elif isinstance(level, int):
            return level
        elif isinstance(level, str):
            return getattr(logging, level.upper())
        return logging.INFO

    def to_dict(self, exclude_sensitive: bool = True) -> Dict[str, Any]:
        """导出配置为字典"""
        data = self.model_dump()

        if exclude_sensitive:
            # 排除敏感字段
            sensitive_keys = ['remote_token']
            for key in sensitive_keys:
                data.pop(key, None)

        return data

    def to_yaml(self, path: Optional[Path] = None, exclude_sensitive: bool = True) -> Optional[str]:
        """导出为YAML格式"""
        import yaml
        data = self.to_dict(exclude_sensitive=exclude_sensitive)
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True)

        if path:
            path.write_text(yaml_str, encoding='utf-8')
            return None
        return yaml_str

    def is_equivalent_to(self, other: 'LoggingConfig') -> bool:
        """判断两个配置是否等效（忽略运行时状态）"""
        return self.get_config_digest() == other.get_config_digest()


    def diff(self, other: 'LoggingConfig') -> Dict[str, tuple]:
        """比较两个配置的差异"""
        current = self.model_dump()
        other_dict = other.model_dump()

        differences = {}
        for key in set(current.keys()) | set(other_dict.keys()):
            if key.startswith('_'):  # 忽略私有属性
                continue
            if current.get(key) != other_dict.get(key):
                differences[key] = (current.get(key), other_dict.get(key))

        return differences

    def validate_all(self) -> Dict[str, Any]:
        """全面验证配置，返回验证报告"""
        report = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'info': {}
        }

        # 检查日志目录权限
        try:
            self.ensure_log_dirs()
        except Exception as e:
            report['errors'].append(f"日志目录创建失败: {e}")
            report['valid'] = False

        # 检查采样配置
        if self.sampling_rate < 1.0 and self.sampling_interval > 0:
            report['warnings'].append("同时设置了 sampling_rate 和 sampling_interval，可能导致日志采样不符合预期")

        # 检查文件大小
        if self.max_bytes < 1024 * 1024:  # 小于1MB
            report['warnings'].append(f"max_bytes 设置过小 ({self.max_bytes})，可能导致频繁的文件轮转")

        # 检查备份数量
        if self.backup_count > 100:
            report['warnings'].append(f"backup_count 设置过大 ({self.backup_count})，可能占用过多磁盘空间")

        # 检查保留天数
        if self.retention_days < 7:
            report['warnings'].append(f"retention_days 设置过小 ({self.retention_days})，日志可能过早被清理")

        # 检查归档配置
        if self.archive_enabled:
            archive_path = Path(self.archive_path)
            if not archive_path.is_absolute():
                archive_path = (self._base_dir or BASE_DIR) / archive_path

            if archive_path.exists() and not os.access(archive_path, os.W_OK):
                report['errors'].append(f"归档目录不可写: {archive_path}")
                report['valid'] = False

        return report