# datamind/config/settings.py

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