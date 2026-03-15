# datamind/config/settings.py
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置类"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # 应用基本信息
    APP_NAME: str = Field(
        default="Datamind",
        validation_alias="DATAMIND_APP_NAME",
        description="应用名称"
    )
    VERSION: str = Field(
        default="1.0.0",
        validation_alias="DATAMIND_VERSION",
        description="应用版本"
    )
    ENV: str = Field(
        default="development",
        validation_alias="DATAMIND_ENV",
        description="运行环境: development/testing/staging/production"
    )
    DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_DEBUG",
        description="调试模式"
    )

    # API配置
    API_HOST: str = Field(
        default="0.0.0.0",
        validation_alias="DATAMIND_API_HOST",
        description="API监听地址"
    )
    API_PORT: int = Field(
        default=8000,
        validation_alias="DATAMIND_API_PORT",
        description="API监听端口"
    )
    API_PREFIX: str = Field(
        default="/api/v1",
        validation_alias="DATAMIND_API_PREFIX",
        description="API路由前缀"
    )
    API_ROOT_PATH: str = Field(
        default="",
        validation_alias="DATAMIND_API_ROOT_PATH",
        description="API根路径（用于反向代理）"
    )

    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/datamind",
        validation_alias="DATAMIND_DATABASE_URL",
        description="PostgreSQL数据库连接URL"
    )
    READONLY_DATABASE_URL: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_READONLY_DATABASE_URL",
        description="只读数据库连接URL（可选）"
    )
    DB_POOL_SIZE: int = Field(
        default=20,
        validation_alias="DATAMIND_DB_POOL_SIZE",
        description="数据库连接池大小"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=40,
        validation_alias="DATAMIND_DB_MAX_OVERFLOW",
        description="数据库连接池最大溢出数"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        validation_alias="DATAMIND_DB_POOL_TIMEOUT",
        description="数据库连接池超时时间（秒）"
    )
    DB_POOL_RECYCLE: int = Field(
        default=3600,
        validation_alias="DATAMIND_DB_POOL_RECYCLE",
        description="数据库连接回收时间（秒）"
    )
    DB_ECHO: bool = Field(
        default=False,
        validation_alias="DATAMIND_DB_ECHO",
        description="是否打印SQL语句"
    )

    # Redis配置
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="DATAMIND_REDIS_URL",
        description="Redis连接URL"
    )
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_REDIS_PASSWORD",
        description="Redis密码"
    )
    REDIS_MAX_CONNECTIONS: int = Field(
        default=50,
        validation_alias="DATAMIND_REDIS_MAX_CONNECTIONS",
        description="Redis最大连接数"
    )
    REDIS_SOCKET_TIMEOUT: int = Field(
        default=5,
        validation_alias="DATAMIND_REDIS_SOCKET_TIMEOUT",
        description="Redis套接字超时（秒）"
    )

    # 存储类型
    STORAGE_TYPE: Literal["local", "minio", "s3"] = Field(
        default="local",
        validation_alias="DATAMIND_STORAGE_TYPE",
        description="存储类型: local(本地存储), minio(MinIO存储), s3(AWS S3兼容存储)"
    )

    # 本地存储配置
    LOCAL_STORAGE_PATH: str = Field(
        default="./models",
        validation_alias="DATAMIND_LOCAL_STORAGE_PATH",
        description="本地存储路径（仅当STORAGE_TYPE=local时使用）"
    )

    # MinIO存储配置
    MINIO_ENDPOINT: str = Field(
        default="localhost:9000",
        validation_alias="MINIO_ENDPOINT",
        description="MinIO服务端点"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin",
        validation_alias="MINIO_ACCESS_KEY",
        description="MinIO访问密钥"
    )
    MINIO_SECRET_KEY: str = Field(
        default="minioadmin",
        validation_alias="MINIO_SECRET_KEY",
        description="MinIO秘密密钥"
    )
    MINIO_BUCKET: str = Field(
        default="datamind-storage",
        validation_alias="MINIO_BUCKET",
        description="MinIO存储桶名称"
    )
    MINIO_SECURE: bool = Field(
        default=False,
        validation_alias="MINIO_SECURE",
        description="是否使用HTTPS连接MinIO"
    )
    MINIO_REGION: Optional[str] = Field(
        default=None,
        validation_alias="MINIO_REGION",
        description="MinIO区域"
    )
    MINIO_LOCATION: str = Field(
        default="us-east-1",
        validation_alias="MINIO_LOCATION",
        description="MinIO存储桶位置"
    )

    # AWS S3存储配置
    S3_ENDPOINT: Optional[str] = Field(
        default=None,
        validation_alias="S3_ENDPOINT",
        description="S3自定义端点（用于兼容S3的其他服务，如OSS、COS等）"
    )
    S3_ACCESS_KEY_ID: str = Field(
        default="",
        validation_alias="AWS_ACCESS_KEY_ID",
        description="AWS访问密钥ID"
    )
    S3_SECRET_ACCESS_KEY: str = Field(
        default="",
        validation_alias="AWS_SECRET_ACCESS_KEY",
        description="AWS秘密访问密钥"
    )
    S3_BUCKET: str = Field(
        default="datamind-storage",
        validation_alias="S3_BUCKET",
        description="S3存储桶名称"
    )
    S3_REGION: str = Field(
        default="us-east-1",
        validation_alias="AWS_REGION",
        description="AWS区域"
    )
    S3_PREFIX: str = Field(
        default="models/",
        validation_alias="S3_PREFIX",
        description="S3对象键前缀"
    )
    S3_ACL: Optional[str] = Field(
        default=None,
        validation_alias="S3_ACL",
        description="S3对象ACL（如 'private', 'public-read'）"
    )
    S3_USE_SSL: bool = Field(
        default=True,
        validation_alias="S3_USE_SSL",
        description="是否使用SSL连接S3"
    )
    S3_VERIFY_SSL: bool = Field(
        default=True,
        validation_alias="S3_VERIFY_SSL",
        description="是否验证SSL证书"
    )
    S3_ADDRESSING_STYLE: Literal["auto", "virtual", "path"] = Field(
        default="auto",
        validation_alias="S3_ADDRESSING_STYLE",
        description="S3寻址风格"
    )
    S3_MAX_POOL_CONNECTIONS: int = Field(
        default=10,
        validation_alias="S3_MAX_POOL_CONNECTIONS",
        description="S3连接池最大连接数"
    )
    S3_TIMEOUT: int = Field(
        default=30,
        validation_alias="S3_TIMEOUT",
        description="S3请求超时时间（秒）"
    )
    S3_RETRIES: int = Field(
        default=3,
        validation_alias="S3_RETRIES",
        description="S3请求重试次数"
    )

    # 存储通用配置
    STORAGE_DEFAULT_TTL: int = Field(
        default=86400,  # 24小时
        validation_alias="DATAMIND_STORAGE_DEFAULT_TTL",
        description="存储对象默认过期时间（秒）"
    )
    STORAGE_ENABLE_CACHE: bool = Field(
        default=True,
        validation_alias="DATAMIND_STORAGE_ENABLE_CACHE",
        description="是否启用存储缓存"
    )
    STORAGE_CACHE_SIZE: int = Field(
        default=100,
        validation_alias="DATAMIND_STORAGE_CACHE_SIZE",
        description="存储缓存大小（对象数量）"
    )
    STORAGE_CACHE_TTL: int = Field(
        default=300,  # 5分钟
        validation_alias="DATAMIND_STORAGE_CACHE_TTL",
        description="存储缓存过期时间（秒）"
    )
    STORAGE_ENABLE_COMPRESSION: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_COMPRESSION",
        description="是否启用存储压缩"
    )
    STORAGE_COMPRESSION_LEVEL: int = Field(
        default=6,
        validation_alias="DATAMIND_STORAGE_COMPRESSION_LEVEL",
        description="存储压缩级别 (1-9)"
    )
    STORAGE_ENABLE_ENCRYPTION: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_ENCRYPTION",
        description="是否启用存储加密"
    )
    STORAGE_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_STORAGE_ENCRYPTION_KEY",
        description="存储加密密钥"
    )
    STORAGE_MAX_FILE_SIZE: int = Field(
        default=1024 * 1024 * 1024,  # 1GB
        validation_alias="DATAMIND_STORAGE_MAX_FILE_SIZE",
        description="存储最大文件大小（字节）"
    )
    STORAGE_ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        validation_alias="DATAMIND_STORAGE_ALLOWED_EXTENSIONS",
        description="允许存储的文件扩展名"
    )
    STORAGE_CHUNK_SIZE: int = Field(
        default=1024 * 1024 * 8,  # 8MB
        validation_alias="DATAMIND_STORAGE_CHUNK_SIZE",
        description="存储分块大小（用于大文件上传）"
    )
    STORAGE_MULTIPART_THRESHOLD: int = Field(
        default=1024 * 1024 * 100,  # 100MB
        validation_alias="DATAMIND_STORAGE_MULTIPART_THRESHOLD",
        description="启用分片上传的阈值"
    )

    # 模型存储配置（向后兼容）
    MODELS_PATH: str = Field(
        default="./models",
        validation_alias="DATAMIND_MODELS_PATH",
        description="模型文件存储路径（本地路径，兼容旧版本）"
    )
    MODEL_FILE_MAX_SIZE: int = Field(
        default=1024 * 1024 * 1024,  # 1GB
        validation_alias="DATAMIND_MODEL_FILE_MAX_SIZE",
        description="模型文件最大大小（字节）"
    )
    ALLOWED_MODEL_EXTENSIONS: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin"],
        validation_alias="DATAMIND_ALLOWED_MODEL_EXTENSIONS",
        description="允许的模型文件扩展名"
    )
    XGBOOST_USE_JSON: bool = Field(
        default=True,
        validation_alias="DATAMIND_XGBOOST_USE_JSON",
        description="XGBoost是否使用JSON格式"
    )

    # 认证配置
    API_KEY_ENABLED: bool = Field(
        default=True,
        validation_alias="DATAMIND_API_KEY_ENABLED",
        description="是否启用API密钥认证"
    )
    API_KEY_HEADER: str = Field(
        default="X-API-Key",
        validation_alias="DATAMIND_API_KEY_HEADER",
        description="API密钥头字段"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        validation_alias="DATAMIND_JWT_SECRET_KEY",
        description="JWT密钥"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias="DATAMIND_JWT_ALGORITHM",
        description="JWT算法"
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        validation_alias="DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        description="JWT访问令牌过期时间（分钟）"
    )

    # ==================== 日志配置 - 与logging_config.py完全兼容 ====================
    # 基本配置
    LOG_NAME: str = Field(
        default="Datamind",
        validation_alias="DATAMIND_LOG_NAME",
        description="日志记录器名称"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias="DATAMIND_LOG_LEVEL",
        description="日志级别: DEBUG/INFO/WARNING/ERROR/CRITICAL"
    )
    LOG_ENCODING: str = Field(
        default="utf-8",
        validation_alias="DATAMIND_LOG_ENCODING",
        description="日志文件编码"
    )

    # 调试配置
    LOG_FORMATTER_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FORMATTER_DEBUG",
        description="是否启用格式化器调试输出"
    )
    LOG_MANAGER_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_MANAGER_DEBUG",
        description="是否启用管理器调试输出"
    )
    LOG_HANDLER_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_HANDLER_DEBUG",
        description="是否启用句柄调试输出"
    )
    LOG_FILTER_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_FILTER_DEBUG",
        description="是否启用过滤器调试输出"
    )
    LOG_CONTEXT_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CONTEXT_DEBUG",
        description="是否启用上下文调试输出"
    )
    LOG_CLEANUP_DEBUG: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_CLEANUP_DEBUG",
        description="是否启用清理管理器调试输出"
    )

    # 时间格式配置
    LOG_TIMEZONE: str = Field(
        default="UTC",
        validation_alias="DATAMIND_LOG_TIMEZONE",
        description="日志时区: UTC/LOCAL/CST/EST/PST"
    )
    LOG_TIMESTAMP_PRECISION: str = Field(
        default="milliseconds",
        validation_alias="DATAMIND_LOG_TIMESTAMP_PRECISION",
        description="时间戳精度: seconds/milliseconds/microseconds/nanoseconds"
    )

    # 文本日志时间格式
    TEXT_DATE_FORMAT: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        validation_alias="DATAMIND_TEXT_DATE_FORMAT",
        description="文本日志日期格式"
    )
    TEXT_DATETIME_FORMAT: str = Field(
        default="%Y-%m-%d %H:%M:%S.%f",
        validation_alias="DATAMIND_TEXT_DATETIME_FORMAT",
        description="文本日志完整时间格式"
    )

    # JSON日志时间格式
    JSON_TIMESTAMP_FIELD: str = Field(
        default="@timestamp",
        validation_alias="DATAMIND_JSON_TIMESTAMP_FIELD",
        description="JSON日志时间字段名"
    )
    JSON_DATE_FORMAT: str = Field(
        default="yyyy-MM-dd",
        validation_alias="DATAMIND_JSON_DATE_FORMAT",
        description="JSON日志日期格式（Java格式）"
    )
    JSON_DATETIME_FORMAT: str = Field(
        default="yyyy-MM-dd'T'HH:mm:ss.SSSZ",
        validation_alias="DATAMIND_JSON_DATETIME_FORMAT",
        description="JSON日志时间格式（Java格式，ISO8601）"
    )
    JSON_USE_EPOCH: bool = Field(
        default=False,
        validation_alias="DATAMIND_JSON_USE_EPOCH",
        description="JSON日志使用时间戳"
    )
    JSON_EPOCH_UNIT: str = Field(
        default="milliseconds",
        validation_alias="DATAMIND_JSON_EPOCH_UNIT",
        description="时间戳单位：seconds/milliseconds/microseconds/nanoseconds"
    )

    # 日志文件名时间格式
    FILE_NAME_TIMESTAMP: bool = Field(
        default=True,
        validation_alias="DATAMIND_FILE_NAME_TIMESTAMP",
        description="日志文件名是否包含时间戳"
    )
    FILE_NAME_DATE_FORMAT: str = Field(
        default="%Y%m%d",
        validation_alias="DATAMIND_FILE_NAME_DATE_FORMAT",
        description="日志文件名日期格式"
    )
    FILE_NAME_DATETIME_FORMAT: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_FILE_NAME_DATETIME_FORMAT",
        description="日志文件名完整时间格式"
    )

    # 文件轮转时间相关
    LOG_ROTATION_AT_TIME: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_ROTATION_AT_TIME",
        description="定时轮转时间，如 '23:59'"
    )
    LOG_ROTATION_UTC: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ROTATION_UTC",
        description="轮转时间是否使用UTC"
    )

    # 旧日志清理时间
    LOG_RETENTION_DAYS: int = Field(
        default=90,
        validation_alias="DATAMIND_LOG_RETENTION_DAYS",
        description="日志保留天数"
    )
    LOG_CLEANUP_AT_TIME: str = Field(
        default="03:00",
        validation_alias="DATAMIND_LOG_CLEANUP_AT_TIME",
        description="日志清理时间"
    )

    # 时间偏移
    LOG_TIME_OFFSET_HOURS: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_TIME_OFFSET_HOURS",
        description="日志时间偏移小时数"
    )

    # 文件配置
    LOG_FILE: str = Field(
        default="logs/Datamind.log",
        validation_alias="DATAMIND_LOG_FILE",
        description="日志文件路径"
    )
    ERROR_LOG_FILE: Optional[str] = Field(
        default="logs/Datamind.error.log",
        validation_alias="DATAMIND_ERROR_LOG_FILE",
        description="错误日志单独文件"
    )

    # 日志格式
    LOG_FORMAT: str = Field(
        default="json",
        validation_alias="DATAMIND_LOG_FORMAT",
        description="日志格式：text/json/both"
    )
    TEXT_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
        validation_alias="DATAMIND_TEXT_FORMAT",
        description="文本日志格式"
    )
    JSON_FORMAT: Dict[str, str] = Field(
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
    TEXT_SUFFIX: str = Field(
        default="text",
        validation_alias="DATAMIND_TEXT_SUFFIX",
        description="文本日志文件后缀"
    )
    JSON_SUFFIX: str = Field(
        default="json",
        validation_alias="DATAMIND_JSON_SUFFIX",
        description="JSON日志文件后缀"
    )

    # 文件轮转配置（按大小）
    LOG_MAX_BYTES: int = Field(
        default=104857600,  # 100MB
        validation_alias="DATAMIND_LOG_MAX_BYTES",
        description="单个日志文件最大字节数"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=30,
        validation_alias="DATAMIND_LOG_BACKUP_COUNT",
        description="备份文件数量"
    )

    # 时间轮转配置
    LOG_ROTATION_WHEN: Optional[str] = Field(
        default="MIDNIGHT",
        validation_alias="DATAMIND_LOG_ROTATION_WHEN",
        description="日志轮转时间单位: S/M/H/D/MIDNIGHT/W0-W6"
    )
    LOG_ROTATION_INTERVAL: int = Field(
        default=1,
        validation_alias="DATAMIND_LOG_ROTATION_INTERVAL",
        description="日志轮转间隔"
    )

    # 并发处理
    LOG_USE_CONCURRENT: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_USE_CONCURRENT",
        description="是否使用并发安全的日志处理器"
    )
    LOG_LOCK_DIR: str = Field(
        default="/tmp/datamind-logs",
        validation_alias="DATAMIND_LOG_LOCK_DIR",
        description="并发日志锁目录"
    )

    # 异步日志
    LOG_ASYNC: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ASYNC",
        description="是否使用异步日志"
    )
    LOG_QUEUE_SIZE: int = Field(
        default=10000,
        validation_alias="DATAMIND_LOG_QUEUE_SIZE",
        description="异步队列大小"
    )

    # 日志采样
    LOG_SAMPLING_RATE: float = Field(
        default=1.0,
        validation_alias="DATAMIND_LOG_SAMPLING_RATE",
        description="日志采样率 (0.0-1.0)"
    )
    LOG_SAMPLING_INTERVAL: int = Field(
        default=0,
        validation_alias="DATAMIND_LOG_SAMPLING_INTERVAL",
        description="采样间隔（秒），0表示不限制"
    )

    # 敏感信息脱敏
    LOG_MASK_SENSITIVE: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_MASK_SENSITIVE",
        description="是否脱敏敏感信息"
    )
    SENSITIVE_FIELDS: List[str] = Field(
        default_factory=lambda: ["id_number", "phone", "card_number", "password", "token"],
        validation_alias="DATAMIND_SENSITIVE_FIELDS",
        description="需要脱敏的字段"
    )
    LOG_MASK_CHAR: str = Field(
        default="*",
        validation_alias="DATAMIND_LOG_MASK_CHAR",
        description="脱敏字符"
    )

    # 日志分类
    LOG_ENABLE_ACCESS: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ACCESS",
        description="是否记录访问日志"
    )
    ACCESS_LOG_FILE: str = Field(
        default="logs/access.log",
        validation_alias="DATAMIND_ACCESS_LOG_FILE",
        description="访问日志文件"
    )

    LOG_ENABLE_AUDIT: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_AUDIT",
        description="是否记录审计日志"
    )
    AUDIT_LOG_FILE: str = Field(
        default="logs/audit.log",
        validation_alias="DATAMIND_AUDIT_LOG_FILE",
        description="审计日志文件"
    )

    LOG_ENABLE_PERFORMANCE: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_PERFORMANCE",
        description="是否记录性能日志"
    )
    PERFORMANCE_LOG_FILE: str = Field(
        default="logs/performance.log",
        validation_alias="DATAMIND_PERFORMANCE_LOG_FILE",
        description="性能日志文件"
    )

    # 日志过滤
    LOG_FILTERS: Dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_paths": ["/health", "/metrics"],
            "exclude_status_codes": [404],
            "min_duration_ms": 0
        },
        validation_alias="DATAMIND_LOG_FILTERS",
        description="日志过滤器"
    )

    # 远程日志
    LOG_ENABLE_REMOTE: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_REMOTE",
        description="是否启用远程日志"
    )
    LOG_REMOTE_URL: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_URL",
        description="远程日志URL"
    )
    LOG_REMOTE_TOKEN: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_LOG_REMOTE_TOKEN",
        description="远程日志认证令牌"
    )
    LOG_REMOTE_TIMEOUT: int = Field(
        default=5,
        validation_alias="DATAMIND_LOG_REMOTE_TIMEOUT",
        description="远程日志超时时间（秒）"
    )
    LOG_REMOTE_BATCH_SIZE: int = Field(
        default=100,
        validation_alias="DATAMIND_LOG_REMOTE_BATCH_SIZE",
        description="远程日志批量发送大小"
    )

    # 控制台输出
    LOG_CONSOLE_OUTPUT: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_CONSOLE",
        description="是否输出到控制台"
    )
    LOG_CONSOLE_LEVEL: str = Field(
        default="INFO",
        validation_alias="DATAMIND_LOG_CONSOLE_LEVEL",
        description="控制台输出级别"
    )

    # 归档配置
    LOG_ARCHIVE_ENABLED: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_ARCHIVE",
        description="是否启用日志归档"
    )
    LOG_ARCHIVE_PATH: str = Field(
        default="/data/logs/archive",
        validation_alias="DATAMIND_LOG_ARCHIVE_PATH",
        description="日志归档路径"
    )
    LOG_ARCHIVE_COMPRESSION: str = Field(
        default="gz",
        validation_alias="DATAMIND_LOG_COMPRESSION",
        description="归档压缩格式"
    )
    LOG_ARCHIVE_NAME_FORMAT: str = Field(
        default="%Y%m%d_%H%M%S",
        validation_alias="DATAMIND_ARCHIVE_NAME_FORMAT",
        description="归档文件名时间格式"
    )

    # A/B测试配置
    AB_TEST_ENABLED: bool = Field(
        default=True,
        validation_alias="DATAMIND_AB_TEST_ENABLED",
        description="是否启用A/B测试"
    )
    AB_TEST_REDIS_KEY_PREFIX: str = Field(
        default="ab_test:",
        validation_alias="DATAMIND_AB_TEST_REDIS_KEY_PREFIX",
        description="A/B测试Redis键前缀"
    )
    AB_TEST_ASSIGNMENT_EXPIRY: int = Field(
        default=86400,  # 24小时
        validation_alias="DATAMIND_AB_TEST_ASSIGNMENT_EXPIRY",
        description="A/B测试分配过期时间（秒）"
    )

    # 监控配置
    METRICS_ENABLED: bool = Field(
        default=True,
        validation_alias="DATAMIND_METRICS_ENABLED",
        description="是否启用监控指标"
    )
    PROMETHEUS_PORT: int = Field(
        default=9090,
        validation_alias="DATAMIND_PROMETHEUS_PORT",
        description="Prometheus指标端口"
    )
    METRICS_PATH: str = Field(
        default="/metrics",
        validation_alias="DATAMIND_METRICS_PATH",
        description="指标路径"
    )

    # 安全配置
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        validation_alias="DATAMIND_CORS_ORIGINS",
        description="CORS允许的源"
    )
    TRUSTED_PROXIES: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_TRUSTED_PROXIES",
        description="可信代理IP列表"
    )
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        validation_alias="DATAMIND_RATE_LIMIT_ENABLED",
        description="是否启用速率限制"
    )
    RATE_LIMIT_REQUESTS: int = Field(
        default=100,
        validation_alias="DATAMIND_RATE_LIMIT_REQUESTS",
        description="速率限制请求数"
    )
    RATE_LIMIT_PERIOD: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_PERIOD",
        description="速率限制周期（秒）"
    )

    # 模型推理配置
    MODEL_INFERENCE_TIMEOUT: int = Field(
        default=30,
        validation_alias="DATAMIND_MODEL_INFERENCE_TIMEOUT",
        description="模型推理超时时间（秒）"
    )
    MODEL_CACHE_SIZE: int = Field(
        default=10,
        validation_alias="DATAMIND_MODEL_CACHE_SIZE",
        description="模型缓存大小"
    )
    MODEL_CACHE_TTL: int = Field(
        default=3600,
        validation_alias="DATAMIND_MODEL_CACHE_TTL",
        description="模型缓存过期时间（秒）"
    )

    # 特征存储配置
    FEATURE_STORE_ENABLED: bool = Field(
        default=True,
        validation_alias="DATAMIND_FEATURE_STORE_ENABLED",
        description="是否启用特征存储"
    )
    FEATURE_CACHE_SIZE: int = Field(
        default=1000,
        validation_alias="DATAMIND_FEATURE_CACHE_SIZE",
        description="特征缓存大小"
    )
    FEATURE_CACHE_TTL: int = Field(
        default=300,
        validation_alias="DATAMIND_FEATURE_CACHE_TTL",
        description="特征缓存过期时间（秒）"
    )

    # 批处理配置
    BATCH_SIZE: int = Field(
        default=100,
        validation_alias="DATAMIND_BATCH_SIZE",
        description="批处理大小"
    )
    MAX_WORKERS: int = Field(
        default=10,
        validation_alias="DATAMIND_MAX_WORKERS",
        description="最大工作线程数"
    )

    # 告警配置
    ALERT_ENABLED: bool = Field(
        default=False,
        validation_alias="DATAMIND_ALERT_ENABLED",
        description="是否启用告警"
    )
    ALERT_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_ALERT_WEBHOOK_URL",
        description="告警Webhook URL"
    )
    ALERT_ON_ERROR: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_ERROR",
        description="错误时是否告警"
    )
    ALERT_ON_MODEL_DEGRADATION: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_MODEL_DEGRADATION",
        description="模型性能下降时是否告警"
    )

    @field_validator("ENV")
    def validate_env(cls, v):
        """验证环境名称"""
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENV 必须是 {allowed} 之一")
        return v

    @field_validator("LOG_LEVEL", "LOG_CONSOLE_LEVEL")
    def validate_log_level(cls, v):
        """验证日志级别"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"日志级别必须是 {allowed} 之一")
        return v.upper()

    @field_validator("LOG_FORMAT")
    def validate_log_format(cls, v):
        """验证日志格式"""
        allowed = ["text", "json", "both"]
        if v.lower() not in allowed:
            raise ValueError(f"LOG_FORMAT 必须是 {allowed} 之一")
        return v.lower()

    @field_validator("LOG_SAMPLING_RATE")
    def validate_sampling_rate(cls, v):
        """验证采样率"""
        if v < 0 or v > 1:
            raise ValueError("LOG_SAMPLING_RATE 必须在 0 到 1 之间")
        return v

    @field_validator("LOG_MAX_BYTES")
    def validate_max_bytes(cls, v):
        """验证最大字节数"""
        if v < 1024:
            raise ValueError("LOG_MAX_BYTES 不能小于1KB")
        return v

    @field_validator("JSON_EPOCH_UNIT")
    def validate_json_epoch_unit(cls, v):
        """验证JSON时间戳单位"""
        valid_units = ['seconds', 'milliseconds', 'microseconds', 'nanoseconds']
        if v not in valid_units:
            raise ValueError(f"JSON_EPOCH_UNIT 必须是 {valid_units} 之一")
        return v

    @field_validator("LOG_ROTATION_AT_TIME")
    def validate_rotation_at_time(cls, v):
        """验证轮转时间格式"""
        if v is not None:
            import re
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError("LOG_ROTATION_AT_TIME 必须是 HH:MM 格式，如 '23:59'")
        return v

    @field_validator("LOG_TIMESTAMP_PRECISION")
    def validate_timestamp_precision(cls, v):
        """验证时间戳精度"""
        allowed = ["seconds", "milliseconds", "microseconds", "nanoseconds"]
        if v not in allowed:
            raise ValueError(f"LOG_TIMESTAMP_PRECISION 必须是 {allowed} 之一")
        return v

    @field_validator("LOG_TIMEZONE")
    def validate_timezone(cls, v):
        """验证时区"""
        allowed = ["UTC", "LOCAL", "CST", "EST", "PST"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_TIMEZONE 必须是 {allowed} 之一")
        return v.upper()

    @field_validator("STORAGE_COMPRESSION_LEVEL")
    def validate_compression_level(cls, v):
        """验证压缩级别"""
        if v < 1 or v > 9:
            raise ValueError("STORAGE_COMPRESSION_LEVEL 必须在 1 到 9 之间")
        return v

    @field_validator("STORAGE_MAX_FILE_SIZE", "MODEL_FILE_MAX_SIZE")
    def validate_max_file_size(cls, v):
        """验证最大文件大小"""
        if v < 1024 * 1024:  # 小于1MB
            raise ValueError("文件大小不能小于1MB")
        return v

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置字典"""
        return {
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "echo": self.DB_ECHO
        }

    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置字典"""
        return {
            "url": self.REDIS_URL,
            "password": self.REDIS_PASSWORD,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置字典（与logging_config.py完全兼容）"""
        return {
            # 基本配置
            "name": self.LOG_NAME,
            "level": self.LOG_LEVEL,
            "encoding": self.LOG_ENCODING,

            # 调试配置
            "formatter_debug": self.LOG_FORMATTER_DEBUG,
            "manager_debug": self.LOG_MANAGER_DEBUG,
            "handler_debug": self.LOG_HANDLER_DEBUG,
            "filter_debug": self.LOG_FILTER_DEBUG,
            "context_debug": self.LOG_CONTEXT_DEBUG,
            "cleanup_debug": self.LOG_CLEANUP_DEBUG,

            # 时间格式配置
            "timezone": self.LOG_TIMEZONE,
            "timestamp_precision": self.LOG_TIMESTAMP_PRECISION,

            # 文本日志时间格式
            "text_date_format": self.TEXT_DATE_FORMAT,
            "text_datetime_format": self.TEXT_DATETIME_FORMAT,

            # JSON日志时间格式
            "json_timestamp_field": self.JSON_TIMESTAMP_FIELD,
            "json_date_format": self.JSON_DATE_FORMAT,
            "json_datetime_format": self.JSON_DATETIME_FORMAT,
            "json_use_epoch": self.JSON_USE_EPOCH,
            "json_epoch_unit": self.JSON_EPOCH_UNIT,

            # 日志文件名时间格式
            "file_name_timestamp": self.FILE_NAME_TIMESTAMP,
            "file_name_date_format": self.FILE_NAME_DATE_FORMAT,
            "file_name_datetime_format": self.FILE_NAME_DATETIME_FORMAT,

            # 文件轮转时间相关
            "rotation_at_time": self.LOG_ROTATION_AT_TIME,
            "rotation_utc": self.LOG_ROTATION_UTC,

            # 旧日志清理时间
            "retention_days": self.LOG_RETENTION_DAYS,
            "cleanup_at_time": self.LOG_CLEANUP_AT_TIME,

            # 时间偏移
            "time_offset_hours": self.LOG_TIME_OFFSET_HOURS,

            # 文件配置
            "file": self.LOG_FILE,
            "error_file": self.ERROR_LOG_FILE,

            # 日志格式
            "format": self.LOG_FORMAT,
            "text_format": self.TEXT_FORMAT,
            "json_format": self.JSON_FORMAT,

            # 日志文件后缀
            "text_suffix": self.TEXT_SUFFIX,
            "json_suffix": self.JSON_SUFFIX,

            # 文件轮转配置
            "max_bytes": self.LOG_MAX_BYTES,
            "backup_count": self.LOG_BACKUP_COUNT,

            # 时间轮转配置
            "rotation_when": self.LOG_ROTATION_WHEN,
            "rotation_interval": self.LOG_ROTATION_INTERVAL,

            # 并发处理
            "use_concurrent": self.LOG_USE_CONCURRENT,
            "concurrent_lock_dir": self.LOG_LOCK_DIR,

            # 异步日志
            "use_async": self.LOG_ASYNC,
            "async_queue_size": self.LOG_QUEUE_SIZE,

            # 日志采样
            "sampling_rate": self.LOG_SAMPLING_RATE,
            "sampling_interval": self.LOG_SAMPLING_INTERVAL,

            # 敏感信息脱敏
            "mask_sensitive": self.LOG_MASK_SENSITIVE,
            "sensitive_fields": self.SENSITIVE_FIELDS,
            "mask_char": self.LOG_MASK_CHAR,

            # 日志分类
            "enable_access_log": self.LOG_ENABLE_ACCESS,
            "access_log_file": self.ACCESS_LOG_FILE,
            "enable_audit_log": self.LOG_ENABLE_AUDIT,
            "audit_log_file": self.AUDIT_LOG_FILE,
            "enable_performance_log": self.LOG_ENABLE_PERFORMANCE,
            "performance_log_file": self.PERFORMANCE_LOG_FILE,

            # 日志过滤
            "filters": self.LOG_FILTERS,

            # 远程日志
            "enable_remote": self.LOG_ENABLE_REMOTE,
            "remote_url": self.LOG_REMOTE_URL,
            "remote_token": self.LOG_REMOTE_TOKEN,
            "remote_timeout": self.LOG_REMOTE_TIMEOUT,
            "remote_batch_size": self.LOG_REMOTE_BATCH_SIZE,

            # 控制台输出
            "console_output": self.LOG_CONSOLE_OUTPUT,
            "console_level": self.LOG_CONSOLE_LEVEL,

            # 归档配置
            "archive_enabled": self.LOG_ARCHIVE_ENABLED,
            "archive_path": self.LOG_ARCHIVE_PATH,
            "archive_compression": self.LOG_ARCHIVE_COMPRESSION,
            "archive_name_format": self.LOG_ARCHIVE_NAME_FORMAT,
        }

    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置字典"""
        config = {
            "type": self.STORAGE_TYPE,
            "default_ttl": self.STORAGE_DEFAULT_TTL,
            "enable_cache": self.STORAGE_ENABLE_CACHE,
            "cache_size": self.STORAGE_CACHE_SIZE,
            "cache_ttl": self.STORAGE_CACHE_TTL,
            "enable_compression": self.STORAGE_ENABLE_COMPRESSION,
            "compression_level": self.STORAGE_COMPRESSION_LEVEL,
            "enable_encryption": self.STORAGE_ENABLE_ENCRYPTION,
            "encryption_key": self.STORAGE_ENCRYPTION_KEY,
            "max_file_size": self.STORAGE_MAX_FILE_SIZE,
            "allowed_extensions": self.STORAGE_ALLOWED_EXTENSIONS,
            "chunk_size": self.STORAGE_CHUNK_SIZE,
            "multipart_threshold": self.STORAGE_MULTIPART_THRESHOLD,
        }

        # 根据存储类型添加特定配置
        if self.STORAGE_TYPE == "local":
            config.update({
                "base_path": self.LOCAL_STORAGE_PATH,
            })
        elif self.STORAGE_TYPE == "minio":
            config.update({
                "endpoint": self.MINIO_ENDPOINT,
                "access_key": self.MINIO_ACCESS_KEY,
                "secret_key": self.MINIO_SECRET_KEY,
                "bucket": self.MINIO_BUCKET,
                "secure": self.MINIO_SECURE,
                "region": self.MINIO_REGION,
                "location": self.MINIO_LOCATION,
            })
        elif self.STORAGE_TYPE == "s3":
            config.update({
                "endpoint": self.S3_ENDPOINT,
                "access_key_id": self.S3_ACCESS_KEY_ID,
                "secret_access_key": self.S3_SECRET_ACCESS_KEY,
                "bucket": self.S3_BUCKET,
                "region": self.S3_REGION,
                "prefix": self.S3_PREFIX,
                "acl": self.S3_ACL,
                "use_ssl": self.S3_USE_SSL,
                "verify_ssl": self.S3_VERIFY_SSL,
                "addressing_style": self.S3_ADDRESSING_STYLE,
                "max_pool_connections": self.S3_MAX_POOL_CONNECTIONS,
                "timeout": self.S3_TIMEOUT,
                "retries": self.S3_RETRIES,
            })

        return config

    def get_model_storage_config(self) -> Dict[str, Any]:
        """获取模型存储配置（兼容旧版本）"""
        base_config = self.get_storage_config()
        base_config.update({
            "models_path": self.MODELS_PATH,
            "xgboost_use_json": self.XGBOOST_USE_JSON,
        })
        return base_config

    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENV == "development"

    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.ENV == "testing"

    def is_staging(self) -> bool:
        """是否为预发布环境"""
        return self.ENV == "staging"

    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENV == "production"


# 创建全局配置实例
settings = Settings()

# 确保必要的目录存在
LOG_PATH = Path(settings.LOG_FILE).parent
LOG_PATH.mkdir(parents=True, exist_ok=True)

# 如果是本地存储，确保本地存储目录存在
if settings.STORAGE_TYPE == "local":
    LOCAL_STORAGE_PATH = Path(settings.LOCAL_STORAGE_PATH)
    LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# 向后兼容：确保模型目录存在
MODELS_PATH = Path(settings.MODELS_PATH)
MODELS_PATH.mkdir(parents=True, exist_ok=True)

# 确保日志锁目录存在
if settings.LOG_USE_CONCURRENT:
    LOCK_DIR = Path(settings.LOG_LOCK_DIR)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)