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
  - 安全配置（SecurityConfig）：CORS、速率限制、可信代理
  - 日志配置（LoggingConfig）：日志级别、格式、轮转、脱敏
  - 存储配置（StorageConfig）：S3/MinIO存储配置

配置来源：
  1. 默认值（代码中定义）
  2. .env 文件（通过 SettingsConfigDict 加载）
  3. 环境变量（覆盖 .env 文件）
"""

from functools import lru_cache
from typing import Optional, List
from pathlib import Path
from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logging_config import LoggingConfig
from .storage_config import StorageConfig

BASE_DIR = Path(__file__).resolve().parent.parent


# 应用配置
class AppConfig(BaseSettings):
    """应用基础配置

    定义应用的基本信息，包括名称、版本、运行环境、调试模式等。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    app_name: str = Field(
        default="Datamind",
        validation_alias="DATAMIND_APP_NAME",
        description="应用名称")
    version: str = Field(
        default="1.0.0",
        validation_alias="DATAMIND_VERSION",
        description="应用版本")
    env: str = Field(
        default="development",
        validation_alias="DATAMIND_ENV",
        description="运行环境: development/testing/staging/production")
    debug: bool = Field(
        default=False,
        validation_alias="DATAMIND_DEBUG",
        description="调试模式")

    @field_validator("env")
    def validate_env(cls, v):
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENV 必须是 {allowed}")
        return v


# 模型配置
class ModelConfig(BaseSettings):
    """模型存储配置

    定义模型文件的存储路径、大小限制、支持的扩展名等。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    models_path: str = Field(
        default="./models",
        validation_alias="DATAMIND_MODELS_PATH",
        description="模型文件存储路径（本地路径）")
    max_size: int = Field(
        default=1024 * 1024 * 1024,
        validation_alias="DATAMIND_MODEL_FILE_MAX_SIZE",
        description="模型文件最大大小（字节）")

    allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin"],
        validation_alias="DATAMIND_ALLOWED_MODEL_EXTENSIONS",
        description="允许的模型文件扩展名"
    )

    xgboost_use_json: bool = Field(
        default=True,
        validation_alias="DATAMIND_XGBOOST_USE_JSON",
        description="XGBoost是否使用JSON格式")


# 推理配置
class InferenceConfig(BaseSettings):
    """模型推理配置

    定义推理超时、模型缓存大小和过期时间。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    timeout: int = Field(
        default=30,
        validation_alias="DATAMIND_MODEL_INFERENCE_TIMEOUT",
        description="模型推理超时时间（秒）")
    cache_size: int = Field(
        default=10,
        validation_alias="DATAMIND_MODEL_CACHE_SIZE",
        description="模型缓存大小（个数）")
    cache_ttl: int = Field(
        default=3600,
        validation_alias="DATAMIND_MODEL_CACHE_TTL",
        description="模型缓存过期时间（秒）")


# 特征存储配置
class FeatureStoreConfig(BaseSettings):
    """特征存储配置

    定义特征缓存的启用状态、缓存大小和过期时间。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_FEATURE_STORE_ENABLED",
        description="是否启用特征存储")
    cache_size: int = Field(
        default=1000,
        validation_alias="DATAMIND_FEATURE_CACHE_SIZE",
        description="特征缓存大小（个数）")
    cache_ttl: int = Field(
        default=300,
        validation_alias="DATAMIND_FEATURE_CACHE_TTL",
        description="特征缓存过期时间（秒）")


# AB 测试配置
class ABTestConfig(BaseSettings):
    """A/B测试配置

    定义A/B测试的启用状态、Redis键前缀和分配过期时间。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_AB_TEST_ENABLED",
        description="是否启用A/B测试")
    redis_key_prefix: str = Field(
        default="ab_test:",
        validation_alias="DATAMIND_AB_TEST_REDIS_KEY_PREFIX",
        description="A/B测试Redis键前缀")
    assignment_expiry: int = Field(
        default=86400,
        validation_alias="DATAMIND_AB_TEST_ASSIGNMENT_EXPIRY",
        description="A/B测试分配过期时间（秒）")


# 批处理配置
class BatchConfig(BaseSettings):
    """批处理配置

    定义批处理大小和最大工作线程数。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    batch_size: int = Field(
        default=100,
        validation_alias="DATAMIND_BATCH_SIZE",
        description="批处理大小")
    max_workers: int = Field(
        default=10,
        validation_alias="DATAMIND_MAX_WORKERS",
        description="最大工作线程数")


# API 配置
class ApiConfig(BaseSettings):
    """API服务配置

    定义API服务的监听地址、端口、路由前缀等。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    host: str = Field(
        default="0.0.0.0",
        validation_alias="DATAMIND_API_HOST",
        description="API监听地址")
    port: int = Field(
        default=8000,
        validation_alias="DATAMIND_API_PORT",
        description="API监听端口")
    prefix: str = Field(
        default="/api/v1",
        validation_alias="DATAMIND_API_PREFIX",
        description="API路由前缀")
    root_path: str = Field(
        default="",
        validation_alias="DATAMIND_API_ROOT_PATH",
        description="API根路径（用于反向代理）")


# Database 配置
class DatabaseConfig(BaseSettings):
    """数据库配置

    定义PostgreSQL连接URL、连接池大小、超时等配置。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/datamind",
        validation_alias="DATAMIND_DATABASE_URL",
        description="PostgreSQL数据库连接URL")
    readonly_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_READONLY_DATABASE_URL",
        description="只读数据库连接URL（可选）")

    pool_size: int = Field(
        default=20,
        validation_alias="DATAMIND_DB_POOL_SIZE",
        description="数据库连接池大小")
    max_overflow: int = Field(
        default=40,
        validation_alias="DATAMIND_DB_MAX_OVERFLOW",
        description="数据库连接池最大溢出数")
    pool_timeout: int = Field(
        default=30,
        validation_alias="DATAMIND_DB_POOL_TIMEOUT",
        description="数据库连接池超时时间（秒）")
    pool_recycle: int = Field(
        default=3600,
        validation_alias="DATAMIND_DB_POOL_RECYCLE",
        description="数据库连接回收时间（秒）")
    echo: bool = Field(
        default=False,
        validation_alias="DATAMIND_DB_ECHO",
        description="是否打印SQL语句")


# Redis 配置
class RedisConfig(BaseSettings):
    """Redis配置

    定义Redis连接URL、密码、连接池等配置。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="DATAMIND_REDIS_URL",
        description="Redis连接URL")
    password: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_REDIS_PASSWORD",
        description="Redis密码")

    max_connections: int = Field(
        default=50,
        validation_alias="DATAMIND_REDIS_MAX_CONNECTIONS",
        description="Redis最大连接数")
    socket_timeout: int = Field(
        default=5,
        validation_alias="DATAMIND_REDIS_SOCKET_TIMEOUT",
        description="Redis套接字超时（秒）")


# 认证配置
class AuthConfig(BaseSettings):
    """认证授权配置

    定义API密钥认证和JWT认证的配置。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    api_key_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_API_KEY_ENABLED",
        description="是否启用API密钥认证")
    api_key_header: str = Field(
        default="X-API-Key",
        validation_alias="DATAMIND_API_KEY_HEADER",
        description="API密钥头字段")

    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production",
        validation_alias="DATAMIND_JWT_SECRET_KEY",
        description="JWT密钥")
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="DATAMIND_JWT_ALGORITHM",
        description="JWT算法")
    jwt_expire_minutes: int = Field(
        default=30,
        validation_alias="DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        description="JWT访问令牌过期时间（分钟）")


# 监控配置
class MonitoringConfig(BaseSettings):
    """监控配置

    定义Prometheus监控指标的启用状态和端口。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_METRICS_ENABLED",
        description="是否启用监控指标")
    prometheus_port: int = Field(
        default=9090,
        validation_alias="DATAMIND_PROMETHEUS_PORT",
        description="Prometheus指标端口")
    path: str = Field(
        default="/metrics",
        validation_alias="DATAMIND_METRICS_PATH",
        description="指标路径")


# 告警配置
class AlertConfig(BaseSettings):
    """告警配置

    定义告警的启用状态、Webhook URL和告警条件。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    enabled: bool = Field(
        default=False,
        validation_alias="DATAMIND_ALERT_ENABLED",
        description="是否启用告警")
    webhook_url: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_ALERT_WEBHOOK_URL",
        description="告警Webhook URL")

    on_error: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_ERROR",
        description="错误时是否告警")
    on_model_degradation: bool = Field(
        default=True,
        validation_alias="DATAMIND_ALERT_ON_MODEL_DEGRADATION",
        description="模型性能下降时是否告警")


# 安全配置
class SecurityConfig(BaseSettings):
    """安全配置

    定义CORS、速率限制、可信代理等安全相关配置。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore")

    cors_origins: List[str] = Field(
        default=["*"],
        validation_alias="DATAMIND_CORS_ORIGINS",
        description="CORS允许的源")
    trusted_proxies: List[str] = Field(
        default=[],
        validation_alias="DATAMIND_TRUSTED_PROXIES",
        description="可信代理IP列表")

    rate_limit_enabled: bool = Field(
        default=True,
        validation_alias="DATAMIND_RATE_LIMIT_ENABLED",
        description="是否启用速率限制")
    rate_limit_requests: int = Field(
        default=100,
        validation_alias="DATAMIND_RATE_LIMIT_REQUESTS",
        description="速率限制请求数")
    rate_limit_period: int = Field(
        default=60,
        validation_alias="DATAMIND_RATE_LIMIT_PERIOD",
        description="速率限制周期（秒）")


# 根配置
class Settings(BaseSettings):
    """根配置

    聚合所有子配置，作为配置的顶层入口。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app: AppConfig = Field(default_factory=AppConfig,
                           description="应用基础配置")
    model: ModelConfig = Field(default_factory=ModelConfig,
                               description="模型存储配置")
    inference: InferenceConfig = Field(default_factory=InferenceConfig,
                                       description="模型推理配置")
    feature_store: FeatureStoreConfig = Field(default_factory=FeatureStoreConfig,
                                              description="特征存储配置")
    ab_test: ABTestConfig = Field(default_factory=ABTestConfig,
                                  description="A/B测试配置")
    batch: BatchConfig = Field(default_factory=BatchConfig,
                               description="批处理配置")
    api: ApiConfig = Field(default_factory=ApiConfig,
                           description="API服务配置")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig,
                                     description="数据库配置")
    redis: RedisConfig = Field(default_factory=RedisConfig,
                               description="Redis配置")
    auth: AuthConfig = Field(default_factory=AuthConfig,
                             description="认证授权配置")
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig,
                                         description="监控配置")
    alert: AlertConfig = Field(default_factory=AlertConfig,
                               description="告警配置")
    security: SecurityConfig = Field(default_factory=SecurityConfig,
                                     description="安全配置")

    logging: LoggingConfig = Field(default_factory=LoggingConfig,
                                   description="日志配置")
    storage: StorageConfig = Field(default_factory=StorageConfig,
                                   description="存储配置")


@lru_cache
def get_settings() -> Settings:
    """获取全局配置实例"""
    return Settings()


__all__ = ["get_settings", "BASE_DIR"]