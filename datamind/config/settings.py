# Datamind/datamind/config/settings.py

"""应用配置模块

定义 Datamind 系统的所有配置项，采用分层配置结构，支持环境变量覆盖。

配置层次结构：
  - 根配置（Settings）：聚合所有子配置
  - 应用配置（AppConfig）：应用名称、版本、环境、调试模式
  - 模型配置（ModelConfig）：模型存储路径、文件大小限制、扩展名
  - 推理配置（InferenceConfig）：推理超时、缓存大小、缓存TTL
  - 特征存储配置（FeatureStoreConfig）：特征缓存配置
  - A/B测试配置（ABTestConfig）：Redis键前缀、分配过期时间
  - 批处理配置（BatchConfig）：批处理大小、工作线程数
  - API配置（ApiConfig）：监听地址、端口、路由前缀
  - 数据库配置（DatabaseConfig）：PostgreSQL连接URL、连接池配置
  - Redis配置（RedisConfig）：Redis连接URL、连接池配置
  - 认证配置（AuthConfig）：API密钥、JWT配置
  - 监控配置（MonitoringConfig）：Prometheus指标端口
  - 告警配置（AlertConfig）：Webhook告警、错误告警
  - CORS配置（CORSConfig）：跨域资源共享配置
  - 速率限制配置（RateLimitConfig）：API速率限制配置
  - IP访问控制配置（IPAccessConfig）：IP白名单/黑名单配置
  - 请求验证配置（RequestValidationConfig）：防重放、防篡改配置
  - 安全响应头配置（SecurityHeadersConfig）：安全响应头配置
  - 请求大小限制配置（RequestSizeConfig）：请求体大小限制配置
  - 性能监控配置（PerformanceConfig）：性能监控配置
  - 日志中间件配置（LoggingMiddlewareConfig）：日志中间件配置
  - 敏感数据脱敏配置（SensitiveDataConfig）：敏感数据脱敏配置
  - 日志配置（LoggingConfig）：日志级别、格式、轮转、脱敏
  - 存储配置（StorageConfig）：S3/MinIO存储配置

配置来源：
  1. 默认值（代码中定义）
  2. .env 文件（通过 SettingsConfigDict 加载）
  3. 环境变量（覆盖 .env 文件）
"""

from functools import lru_cache
from typing import Optional, List
from typing import ClassVar
from pathlib import Path
from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logging_config import LoggingConfig
from .storage_config import StorageConfig

BASE_DIR = Path(__file__).resolve().parent.parent


class AppConfig(BaseSettings):
    """应用基础配置

    定义应用的基本信息，包括名称、版本、运行环境、调试模式等。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    app_name: str = Field(
        default="Datamind",
        validation_alias="DATAMIND_APP_NAME",
        description="应用名称"
    )

    version: str = Field(
        default="1.0.0",
        validation_alias="DATAMIND_VERSION",
        description="应用版本"
    )

    env: str = Field(
        default="DEVELOPMENT",
        validation_alias="DATAMIND_ENV",
        description="运行环境: development/testing/staging/production"
    )

    debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_DEBUG",
        description="调试模式"
    )

    @field_validator("env")
    def validate_env(cls, v: str) -> str:
        """验证运行环境是否合法"""
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENV 必须是 {allowed}")
        return v


class ModelConfig(BaseSettings):
    """模型存储配置

    定义模型文件的存储路径、大小限制、支持的扩展名等。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    models_path: str = Field(
        default="./models",
        validation_alias="DATAMIND_MODELS_PATH",
        description="模型文件存储路径（本地路径）"
    )

    max_size: int = Field(
        default=1024 * 1024 * 1024,
        validation_alias="DATAMIND_MODEL_FILE_MAX_SIZE",
        description="模型文件最大大小（字节）"
    )

    allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin"],
        validation_alias="DATAMIND_ALLOWED_MODEL_EXTENSIONS",
        description="允许的模型文件扩展名"
    )

    xgboost_use_json: bool = Field(
        default=True,
        validation_alias="DATAMIND_XGBOOST_USE_JSON",
        description="XGBoost是否使用JSON格式"
    )


class InferenceConfig(BaseSettings):
    """模型推理配置

    定义推理超时、模型缓存大小和过期时间。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    timeout: int = Field(
        default=30,
        validation_alias="DATAMIND_MODEL_INFERENCE_TIMEOUT",
        description="模型推理超时时间（秒）"
    )

    cache_size: int = Field(
        default=10,
        validation_alias="DATAMIND_MODEL_CACHE_SIZE",
        description="模型缓存大小（个数）"
    )

    cache_ttl: int = Field(
        default=3600,
        validation_alias="DATAMIND_MODEL_CACHE_TTL",
        description="模型缓存过期时间（秒）"
    )


class FeatureStoreConfig(BaseSettings):
    """特征存储配置

    定义特征缓存的启用状态、缓存大小和过期时间。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_FEATURE_STORE_ENABLED",
        description="是否启用特征存储"
    )

    cache_size: int = Field(
        default=1000,
        validation_alias="DATAMIND_FEATURE_CACHE_SIZE",
        description="特征缓存大小（个数）"
    )

    cache_ttl: int = Field(
        default=300,
        validation_alias="DATAMIND_FEATURE_CACHE_TTL",
        description="特征缓存过期时间（秒）"
    )


class ABTestConfig(BaseSettings):
    """A/B测试配置

    定义A/B测试的启用状态、Redis键前缀和分配过期时间。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_AB_TEST_ENABLED",
        description="是否启用A/B测试"
    )

    redis_key_prefix: str = Field(
        default="ab_test:",
        validation_alias="DATAMIND_AB_TEST_REDIS_KEY_PREFIX",
        description="A/B测试Redis键前缀"
    )

    assignment_expiry: int = Field(
        default=86400,
        validation_alias="DATAMIND_AB_TEST_ASSIGNMENT_EXPIRY",
        description="A/B测试分配过期时间（秒）"
    )


class BatchConfig(BaseSettings):
    """批处理配置

    定义批处理大小和最大工作线程数。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    batch_size: int = Field(
        default=100,
        validation_alias="DATAMIND_BATCH_SIZE",
        description="批处理大小"
    )

    max_workers: int = Field(
        default=10,
        validation_alias="DATAMIND_MAX_WORKERS",
        description="最大工作线程数"
    )


class ApiConfig(BaseSettings):
    """API服务配置

    定义API服务的监听地址、端口、路由前缀等。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    host: str = Field(
        default="0.0.0.0",
        validation_alias="DATAMIND_API_HOST",
        description="API监听地址"
    )

    port: int = Field(
        default=8000,
        validation_alias="DATAMIND_API_PORT",
        description="API监听端口"
    )

    prefix: str = Field(
        default="/api/v1",
        validation_alias="DATAMIND_API_PREFIX",
        description="API路由前缀"
    )

    root_path: str = Field(
        default="",
        validation_alias="DATAMIND_API_ROOT_PATH",
        description="API根路径（用于反向代理）"
    )

    api_version: str = Field(
        default="v1",
        validation_alias="DATAMIND_API_VERSION",
        description="当前API版本"
    )
    supported_versions: List[str] = Field(
        default=["v1"],
        validation_alias="DATAMIND_SUPPORTED_API_VERSIONS",
        description="支持的API版本列表"
    )
    deprecated_versions: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_DEPRECATED_API_VERSIONS",
        description="已弃用的API版本列表"
    )


class DatabaseConfig(BaseSettings):
    """数据库配置

    定义PostgreSQL连接URL、连接池大小、超时等配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/datamind",
        validation_alias="DATAMIND_DATABASE_URL",
        description="PostgreSQL数据库连接URL"
    )

    readonly_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_READONLY_DATABASE_URL",
        description="只读数据库连接URL（可选）"
    )

    pool_size: int = Field(
        default=20,
        validation_alias="DATAMIND_DB_POOL_SIZE",
        description="数据库连接池大小"
    )

    max_overflow: int = Field(
        default=40,
        validation_alias="DATAMIND_DB_MAX_OVERFLOW",
        description="数据库连接池最大溢出数"
    )

    pool_timeout: int = Field(
        default=30,
        validation_alias="DATAMIND_DB_POOL_TIMEOUT",
        description="数据库连接池超时时间（秒）"
    )

    pool_recycle: int = Field(
        default=3600,
        validation_alias="DATAMIND_DB_POOL_RECYCLE",
        description="数据库连接回收时间（秒）"
    )

    echo: bool = Field(
        default=False,
        validation_alias="DATAMIND_DB_ECHO",
        description="是否打印SQL语句"
    )


class RedisConfig(BaseSettings):
    """Redis配置

    定义Redis连接URL、密码、连接池等配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="DATAMIND_REDIS_URL",
        description="Redis连接URL"
    )

    password: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_REDIS_PASSWORD",
        description="Redis密码"
    )

    max_connections: int = Field(
        default=50,
        validation_alias="DATAMIND_REDIS_MAX_CONNECTIONS",
        description="Redis最大连接数"
    )

    socket_timeout: int = Field(
        default=5,
        validation_alias="DATAMIND_REDIS_SOCKET_TIMEOUT",
        description="Redis套接字超时（秒）"
    )


class AuthConfig(BaseSettings):
    """认证授权配置

    定义API密钥认证和JWT认证的配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    api_key_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_API_KEY_ENABLED",
        description="是否启用API密钥认证"
    )

    api_key_header: str = Field(
        default="X-API-Key",
        validation_alias="DATAMIND_API_KEY_HEADER",
        description="API密钥头字段"
    )

    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production",
        validation_alias="DATAMIND_JWT_SECRET_KEY",
        description="JWT密钥"
    )

    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="DATAMIND_JWT_ALGORITHM",
        description="JWT算法"
    )

    jwt_expire_minutes: int = Field(
        default=30,
        validation_alias="DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        description="JWT访问令牌过期时间（分钟）"
    )


class MonitoringConfig(BaseSettings):
    """监控配置

    定义Prometheus监控指标的启用状态和端口。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_METRICS_ENABLED",
        description="是否启用监控指标"
    )

    prometheus_port: int = Field(
        default=9090,
        validation_alias="DATAMIND_PROMETHEUS_PORT",
        description="Prometheus指标端口"
    )

    path: str = Field(
        default="/metrics",
        validation_alias="DATAMIND_METRICS_PATH",
        description="指标路径"
    )


class AlertConfig(BaseSettings):
    """告警配置

    定义告警的启用状态、Webhook URL和告警条件。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_ALERT_ENABLED",
        description="是否启用告警"
    )

    webhook_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_ALERT_WEBHOOK_URL",
        description="告警Webhook URL"
    )

    on_error: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_ERROR",
        description="错误时是否告警"
    )

    on_model_degradation: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_MODEL_DEGRADATION",
        description="模型性能下降时是否告警"
    )


class CORSConfig(BaseSettings):
    """CORS跨域资源共享配置

    定义跨域请求的允许源、方法、头信息等。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    cors_origins: List[str] = Field(
        default=["*"],
        validation_alias="DATAMIND_CORS_ORIGINS",
        description="CORS允许的源列表"
    )

    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        validation_alias="DATAMIND_CORS_METHODS",
        description="CORS允许的HTTP方法"
    )

    cors_headers: List[str] = Field(
        default=[
            "Content-Type", "Authorization", "X-Request-ID",
            "X-API-Key", "X-Application-ID", "X-Trace-ID",
            "X-Parent-Span-ID", "X-Span-ID", "X-User-ID"
        ],
        validation_alias="DATAMIND_CORS_HEADERS",
        description="CORS允许的请求头"
    )

    cors_expose_headers: List[str] = Field(
        default=[
            "X-Request-ID", "X-Process-Time-MS", "X-RateLimit-Limit",
            "X-RateLimit-Remaining", "X-RateLimit-Reset",
            "X-Trace-ID", "X-Span-ID", "X-Parent-Span-ID", "X-User-ID"
        ],
        validation_alias="DATAMIND_CORS_EXPOSE_HEADERS",
        description="CORS暴露的响应头"
    )

    cors_allow_credentials: bool = Field(
        default=True,
        validation_alias="DATAMIND_CORS_ALLOW_CREDENTIALS",
        description="是否允许携带凭证"
    )

    cors_max_age: int = Field(
        default=600,
        validation_alias="DATAMIND_CORS_MAX_AGE",
        description="预检请求缓存时间（秒）"
    )

    cors_log_requests: bool = Field(
        default=True,
        validation_alias="DATAMIND_CORS_LOG_REQUESTS",
        description="是否记录CORS请求日志"
    )


class RateLimitConfig(BaseSettings):
    """API速率限制配置

    定义不同用户等级的请求频率限制。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    rate_limit_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_RATE_LIMIT_ENABLED",
        description="是否启用速率限制"
    )

    rate_limit_default_limit: int = Field(
        default=100,
        validation_alias="DATAMIND_RATE_LIMIT_DEFAULT_LIMIT",
        description="默认限流次数"
    )

    rate_limit_default_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_DEFAULT_PERIOD",
        description="默认限流周期（秒）"
    )

    rate_limit_admin_limit: int = Field(
        default=1000,
        validation_alias="DATAMIND_RATE_LIMIT_ADMIN_LIMIT",
        description="管理员限流次数"
    )

    rate_limit_admin_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_ADMIN_PERIOD",
        description="管理员限流周期（秒）"
    )

    rate_limit_developer_limit: int = Field(
        default=500,
        validation_alias="DATAMIND_RATE_LIMIT_DEVELOPER_LIMIT",
        description="开发者限流次数"
    )

    rate_limit_developer_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_DEVELOPER_PERIOD",
        description="开发者限流周期（秒）"
    )

    rate_limit_analyst_limit: int = Field(
        default=200,
        validation_alias="DATAMIND_RATE_LIMIT_ANALYST_LIMIT",
        description="分析师限流次数"
    )

    rate_limit_analyst_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_ANALYST_PERIOD",
        description="分析师限流周期（秒）"
    )

    rate_limit_api_user_limit: int = Field(
        default=100,
        validation_alias="DATAMIND_RATE_LIMIT_API_USER_LIMIT",
        description="API用户限流次数"
    )

    rate_limit_api_user_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_API_USER_PERIOD",
        description="API用户限流周期（秒）"
    )

    rate_limit_anonymous_limit: int = Field(
        default=50,
        validation_alias="DATAMIND_RATE_LIMIT_ANONYMOUS_LIMIT",
        description="匿名用户限流次数"
    )

    rate_limit_anonymous_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_ANONYMOUS_PERIOD",
        description="匿名用户限流周期（秒）"
    )


class IPAccessConfig(BaseSettings):
    """IP访问控制配置

    定义IP白名单和黑名单，支持CIDR表示法。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    trusted_proxies: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_TRUSTED_PROXIES",
        description="可信代理IP列表（用于获取真实客户端IP）"
    )

    ip_whitelist: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_IP_WHITELIST",
        description="IP白名单（支持CIDR表示法）"
    )

    ip_blacklist: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_IP_BLACKLIST",
        description="IP黑名单（支持CIDR表示法）"
    )

    ip_whitelist_enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_IP_WHITELIST_ENABLED",
        description="是否启用IP白名单"
    )

    ip_blacklist_enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_IP_BLACKLIST_ENABLED",
        description="是否启用IP黑名单"
    )


class RequestValidationConfig(BaseSettings):
    """请求验证配置

    定义防重放攻击和防篡改的验证机制。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    enable_timestamp_validation: bool = Field(
        default=False,
        validation_alias="DATAMIND_ENABLE_TIMESTAMP_VALIDATION",
        description="是否启用时间戳验证（防重放攻击）"
    )

    enable_signature_validation: bool = Field(
        default=False,
        validation_alias="DATAMIND_ENABLE_SIGNATURE_VALIDATION",
        description="是否启用签名验证（防篡改）"
    )

    timestamp_max_age: int = Field(
        default=300,
        validation_alias="DATAMIND_TIMESTAMP_MAX_AGE",
        description="时间戳最大有效期（秒）"
    )

    validation_exclude_paths: List[str] = Field(
        default=["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
        validation_alias="DATAMIND_VALIDATION_EXCLUDE_PATHS",
        description="排除验证的路径"
    )


class SecurityHeadersConfig(BaseSettings):
    """安全响应头配置

    定义HTTP安全响应头，增强应用安全性。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    security_headers_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_SECURITY_HEADERS_ENABLED",
        description="是否启用安全响应头"
    )

    remove_server_header: bool = Field(
        default=True,
        validation_alias="DATAMIND_REMOVE_SERVER_HEADER",
        description="是否移除Server响应头"
    )

    csp_policy: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_CSP_POLICY",
        description="自定义CSP策略（如果为None则使用默认）"
    )


class RequestSizeConfig(BaseSettings):
    """请求大小限制配置

    定义请求体大小限制，防止恶意大请求消耗资源。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    max_request_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        validation_alias="DATAMIND_MAX_REQUEST_SIZE",
        description="最大请求体大小（字节）"
    )

    size_limit_exclude_paths: List[str] = Field(
        default=["/upload", "/files"],
        validation_alias="DATAMIND_SIZE_LIMIT_EXCLUDE_PATHS",
        description="排除大小限制的路径"
    )


class PerformanceConfig(BaseSettings):
    """性能监控配置

    定义系统性能监控的各项指标和阈值。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    performance_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_PERFORMANCE_ENABLED",
        description="是否启用性能监控"
    )

    performance_detailed: bool = Field(
        default=True,
        validation_alias="DATAMIND_PERFORMANCE_DETAILED",
        description="是否启用详细监控（CPU/内存）"
    )

    performance_concurrent_tracking: bool = Field(
        default=True,
        validation_alias="DATAMIND_PERFORMANCE_CONCURRENT_TRACKING",
        description="是否启用并发请求追踪"
    )

    performance_db_tracking: bool = Field(
        default=False,
        validation_alias="DATAMIND_PERFORMANCE_DB_TRACKING",
        description="是否启用数据库查询追踪"
    )

    performance_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        validation_alias="DATAMIND_PERFORMANCE_SAMPLE_RATE",
        description="采样率（0.0-1.0）"
    )

    slow_request_threshold: int = Field(
        default=1000,
        validation_alias="DATAMIND_SLOW_REQUEST_THRESHOLD",
        description="慢请求阈值（毫秒）"
    )

    slow_query_threshold: float = Field(
        default=100.0,
        validation_alias="DATAMIND_SLOW_QUERY_THRESHOLD",
        description="慢查询阈值（毫秒）"
    )

    pg_stat_interval: int = Field(
        default=60,
        validation_alias="DATAMIND_PG_STAT_INTERVAL",
        description="PostgreSQL统计收集间隔（秒）"
    )


class LoggingMiddlewareConfig(BaseSettings):
    """日志中间件配置

    定义HTTP请求/响应日志的记录行为。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    log_request_body: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_REQUEST_BODY",
        description="是否记录请求体"
    )

    log_response_body: bool = Field(
        default=False,
        validation_alias="DATAMIND_LOG_RESPONSE_BODY",
        description="是否记录响应体"
    )

    log_max_body_size: int = Field(
        default=10240,  # 10KB
        validation_alias="DATAMIND_LOG_MAX_BODY_SIZE",
        description="最大记录请求体大小（字节）"
    )

    log_headers: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_HEADERS",
        description="是否记录请求头"
    )

    log_exclude_paths: List[str] = Field(
        default=["/health", "/metrics", "/static", "/favicon.ico", "/docs", "/redoc", "/openapi.json"],
        validation_alias="DATAMIND_LOG_EXCLUDE_PATHS",
        description="排除日志记录的路径"
    )


class SensitiveDataConfig(BaseSettings):
    """敏感数据脱敏配置

    定义需要脱敏的字段和请求头，用于日志记录和安全审计。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # 默认敏感字段 - 使用 ClassVar
    _default_fields: ClassVar[List[str]] = [
        "password", "token", "api_key", "api_secret", "secret",
        "access_token", "refresh_token", "auth_token",
        "credit_card", "creditcard", "card_number", "cvv", "cvc", "cc_number",
        "id_number", "id_card", "ssn", "social_security", "tax_id",
        "phone", "mobile", "telephone", "cellphone",
        "email", "email_address", "mail",
        "private_key", "pem", "certificate",
        "signature", "hmac", "hash"
    ]

    # 默认敏感请求头 - 使用 ClassVar
    _default_headers: ClassVar[List[str]] = [
        "authorization", "cookie", "x-api-key", "x-auth-token",
        "x-secret-key", "x-api-secret", "x-access-token",
        "x-refresh-token", "x-session-token", "x-signature"
    ]

    sensitive_fields: List[str] = Field(
        default_factory=lambda: list(SensitiveDataConfig._default_fields),
        validation_alias="DATAMIND_SENSITIVE_FIELDS",
        description="需要脱敏的字段名列表（会与默认字段合并）"
    )

    sensitive_headers: List[str] = Field(
        default_factory=lambda: list(SensitiveDataConfig._default_headers),
        validation_alias="DATAMIND_SENSITIVE_HEADERS",
        description="需要脱敏的请求头列表（会与默认字段合并）"
    )

    mask_char: str = Field(
        default="*",
        validation_alias="DATAMIND_MASK_CHAR",
        description="脱敏替换字符"
    )

    show_partial: bool = Field(
        default=True,
        validation_alias="DATAMIND_SHOW_PARTIAL",
        description="是否显示部分脱敏内容（如手机号前3后4）"
    )

    @field_validator("sensitive_fields", mode="before")
    @classmethod
    def merge_fields(cls, v):
        """合并自定义字段与默认字段"""
        if v is None:
            return list(cls._default_fields)
        if isinstance(v, str):
            import json
            try:
                custom_fields = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError(f"无效的 JSON 格式: {v}")
        else:
            custom_fields = v

        # 合并
        merged = list(set(cls._default_fields + custom_fields))
        return merged

    @field_validator("sensitive_headers", mode="before")
    @classmethod
    def merge_headers(cls, v):
        """合并自定义请求头与默认请求头"""
        if v is None:
            return list(cls._default_headers)
        if isinstance(v, str):
            import json
            try:
                custom_headers = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError(f"无效的 JSON 格式: {v}")
        else:
            custom_headers = v

        # 合并
        merged = list(set(cls._default_headers + custom_headers))
        return merged


class Settings(BaseSettings):
    """根配置

    聚合所有子配置，作为配置的顶层入口。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 基础配置
    app: AppConfig = Field(
        default_factory=AppConfig,
        description="应用基础配置"
    )

    # 模型相关配置
    model: ModelConfig = Field(
        default_factory=ModelConfig,
        description="模型存储配置"
    )

    inference: InferenceConfig = Field(
        default_factory=InferenceConfig,
        description="模型推理配置"
    )

    feature_store: FeatureStoreConfig = Field(
        default_factory=FeatureStoreConfig,
        description="特征存储配置"
    )

    # A/B测试和批处理配置
    ab_test: ABTestConfig = Field(
        default_factory=ABTestConfig,
        description="A/B测试配置"
    )

    batch: BatchConfig = Field(
        default_factory=BatchConfig,
        description="批处理配置"
    )

    # 网络和API配置
    api: ApiConfig = Field(
        default_factory=ApiConfig,
        description="API服务配置"
    )

    # 数据存储配置
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="数据库配置"
    )

    redis: RedisConfig = Field(
        default_factory=RedisConfig,
        description="Redis配置"
    )

    storage: StorageConfig = Field(
        default_factory=StorageConfig,
        description="存储配置"
    )

    # 认证配置
    auth: AuthConfig = Field(
        default_factory=AuthConfig,
        description="认证授权配置"
    )

    # 监控和告警配置
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig,
        description="监控配置"
    )

    alert: AlertConfig = Field(
        default_factory=AlertConfig,
        description="告警配置"
    )

    # 中间件配置
    cors: CORSConfig = Field(
        default_factory=CORSConfig,
        description="CORS跨域配置"
    )

    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="速率限制配置"
    )

    ip_access: IPAccessConfig = Field(
        default_factory=IPAccessConfig,
        description="IP访问控制配置"
    )

    request_validation: RequestValidationConfig = Field(
        default_factory=RequestValidationConfig,
        description="请求验证配置"
    )

    security_headers: SecurityHeadersConfig = Field(
        default_factory=SecurityHeadersConfig,
        description="安全响应头配置"
    )

    request_size: RequestSizeConfig = Field(
        default_factory=RequestSizeConfig,
        description="请求大小限制配置"
    )

    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig,
        description="性能监控配置"
    )

    logging_middleware: LoggingMiddlewareConfig = Field(
        default_factory=LoggingMiddlewareConfig,
        description="日志中间件配置"
    )

    # 数据处理配置
    sensitive_data: SensitiveDataConfig = Field(
        default_factory=SensitiveDataConfig,
        description="敏感数据脱敏配置"
    )

    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="日志配置"
    )


@lru_cache
def get_settings() -> Settings:
    """获取全局配置实例"""
    return Settings()


__all__ = ["get_settings", "BASE_DIR"]