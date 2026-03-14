# datamind/config/settings.py
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
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

    # 模型存储配置
    MODELS_PATH: str = Field(
        default="./models",
        validation_alias="DATAMIND_MODELS_PATH",
        description="模型文件存储路径"
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

    # 日志配置 - 与logging_config.py配合使用
    LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias="DATAMIND_LOG_LEVEL",
        description="日志级别"
    )
    LOG_FORMAT: str = Field(
        default="json",
        validation_alias="DATAMIND_LOG_FORMAT",
        description="日志格式: text/json/both"
    )
    LOG_PATH: str = Field(
        default="./logs",
        validation_alias="DATAMIND_LOG_PATH",
        description="日志文件路径"
    )
    LOG_MAX_BYTES: int = Field(
        default=104857600,  # 100MB
        validation_alias="DATAMIND_LOG_MAX_BYTES",
        description="单个日志文件最大字节数"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=30,
        validation_alias="DATAMIND_LOG_BACKUP_COUNT",
        description="日志备份文件数量"
    )
    LOG_RETENTION_DAYS: int = Field(
        default=90,
        validation_alias="DATAMIND_LOG_RETENTION_DAYS",
        description="日志保留天数"
    )
    LOG_TIMEZONE: str = Field(
        default="UTC",
        validation_alias="DATAMIND_LOG_TIMEZONE",
        description="日志时区"
    )
    LOG_ENABLE_ACCESS: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ENABLE_ACCESS",
        description="是否启用访问日志"
    )
    LOG_ENABLE_AUDIT: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ENABLE_AUDIT",
        description="是否启用审计日志"
    )
    LOG_ENABLE_PERFORMANCE: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_ENABLE_PERFORMANCE",
        description="是否启用性能日志"
    )
    LOG_MASK_SENSITIVE: bool = Field(
        default=True,
        validation_alias="DATAMIND_LOG_MASK_SENSITIVE",
        description="是否脱敏敏感信息"
    )
    LOG_SAMPLING_RATE: float = Field(
        default=1.0,
        validation_alias="DATAMIND_LOG_SAMPLING_RATE",
        description="日志采样率 (0.0-1.0)"
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

    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """验证日志级别"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL 必须是 {allowed} 之一")
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

    @field_validator("MODEL_FILE_MAX_SIZE")
    def validate_model_file_max_size(cls, v):
        """验证模型文件最大大小"""
        if v < 1024 * 1024:  # 小于1MB
            raise ValueError("MODEL_FILE_MAX_SIZE 不能小于1MB")
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
        """获取日志配置字典（与logging_config.py兼容）"""
        return {
            "level": self.LOG_LEVEL,
            "format": self.LOG_FORMAT,
            "file": f"{self.LOG_PATH}/Datamind.log",
            "error_file": f"{self.LOG_PATH}/Datamind.error.log",
            "access_log_file": f"{self.LOG_PATH}/access.log",
            "audit_log_file": f"{self.LOG_PATH}/audit.log",
            "performance_log_file": f"{self.LOG_PATH}/performance.log",
            "max_bytes": self.LOG_MAX_BYTES,
            "backup_count": self.LOG_BACKUP_COUNT,
            "retention_days": self.LOG_RETENTION_DAYS,
            "timezone": self.LOG_TIMEZONE,
            "mask_sensitive": self.LOG_MASK_SENSITIVE,
            "sampling_rate": self.LOG_SAMPLING_RATE
        }

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()

# 确保必要的目录存在
LOG_PATH = Path(settings.LOG_PATH)
LOG_PATH.mkdir(parents=True, exist_ok=True)

MODELS_PATH = Path(settings.MODELS_PATH)
MODELS_PATH.mkdir(parents=True, exist_ok=True)

# MinIO配置
MINIO_ENDPOINT: str = Field("localhost:9000", env="MINIO_ENDPOINT")
MINIO_ACCESS_KEY: str = Field("minioadmin", env="MINIO_ACCESS_KEY")
MINIO_SECRET_KEY: str = Field("minioadmin", env="MINIO_SECRET_KEY")
MINIO_BUCKET: str = Field("datamind-models", env="MINIO_BUCKET")
MINIO_SECURE: bool = Field(False, env="MINIO_SECURE")
MINIO_REGION: Optional[str] = Field(None, env="MINIO_REGION")