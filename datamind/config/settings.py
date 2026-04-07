# datamind/config/settings.py

"""应用配置模块

定义 Datamind 系统的所有配置项，采用分层配置结构，支持环境变量覆盖。

核心功能：
  - get_settings: 获取完整配置对象（懒加载）
  - reload_settings: 运行时重载配置
  - get_logging_config: 获取日志配置子模块
  - get_storage_config: 获取存储配置子模块
  - get_scorecard_config: 获取评分卡配置子模块

特性：
  - 分层设计：根配置聚合所有子配置，职责清晰
  - 环境变量支持：支持 .env 文件和环境变量覆盖
  - 懒加载：配置在首次使用时才初始化
  - 热重载：支持运行时动态刷新配置
  - 线程安全：使用双重检查锁保证并发安全
  - 生产安全：自动验证 JWT、Redis、数据库等安全配置
  - 类型安全：完整的 Pydantic 类型注解和验证
  - 环境枚举：使用 Enum 定义环境，自动校验
  - 辅助属性：提供 is_production/is_development 便捷判断
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from datamind import PROJECT_ROOT
from .logging_config import LoggingConfig
from .storage_config import StorageConfig
from .scorecard_config import ScorecardDefaultConfig


# ==================== 枚举定义 ====================

class Environment(str, Enum):
    """运行环境枚举

    定义系统运行的环境类型。

    - DEVELOPMENT: 开发环境
    - TESTING: 测试环境
    - STAGING: 预发布环境
    - PRODUCTION: 生产环境
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


# ==================== 配置类定义 ====================

class AppConfig(BaseModel):
    """应用基础配置

    定义应用的基本信息，包括名称、版本、运行环境。

    - name: 应用名称
    - version: 应用版本
    - environment: 运行环境（development/testing/staging/production）
    """

    name: str = Field(default="datamind", description="应用名称")
    version: str = Field(default="1.0.0", description="应用版本")
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="运行环境")


class ModelConfig(BaseModel):
    """模型存储配置

    定义模型文件的存储路径、大小限制、支持的扩展名等。

    - models_path: 模型文件存储路径（相对于项目根目录）
    - max_size: 模型文件最大大小（字节）
    - allowed_extensions: 允许的模型文件扩展名列表
    - xgboost_use_json: XGBoost 是否使用 JSON 格式
    """

    models_path: str = Field(
        default="models",
        description="模型文件存储路径（相对于项目根目录）"
    )
    max_size: int = Field(default=1024 * 1024 * 1024, description="模型文件最大大小（字节）")
    allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin"],
        description="允许的模型文件扩展名"
    )
    xgboost_use_json: bool = Field(default=True, description="XGBoost是否使用JSON格式")

    def get_resolved_models_path(self) -> Path:
        """获取解析后的模型存储路径

        返回:
            模型存储目录的 Path 对象
        """
        return PROJECT_ROOT / self.models_path


class InferenceConfig(BaseModel):
    """模型推理配置

    定义推理超时、模型缓存大小和过期时间。

    - timeout: 模型推理超时时间（秒）
    - cache_size: 模型缓存大小（个数）
    - cache_ttl: 模型缓存过期时间（秒）
    """

    timeout: int = Field(default=30, description="模型推理超时时间（秒）")
    cache_size: int = Field(default=10, description="模型缓存大小（个数）")
    cache_ttl: int = Field(default=3600, description="模型缓存过期时间（秒）")


class FeatureStoreConfig(BaseModel):
    """特征存储配置

    定义特征缓存的启用状态、缓存大小和过期时间。

    - enabled: 是否启用特征存储
    - cache_size: 特征缓存大小（个数）
    - cache_ttl: 特征缓存过期时间（秒）
    """

    enabled: bool = Field(default=True, description="是否启用特征存储")
    cache_size: int = Field(default=1000, description="特征缓存大小（个数）")
    cache_ttl: int = Field(default=300, description="特征缓存过期时间（秒）")


class ABTestConfig(BaseModel):
    """A/B测试配置

    定义A/B测试的启用状态、Redis键前缀和分配过期时间。

    - enabled: 是否启用A/B测试
    - redis_key_prefix: A/B测试Redis键前缀
    - assignment_expiry: A/B测试分配过期时间（秒）
    """

    enabled: bool = Field(default=True, description="是否启用A/B测试")
    redis_key_prefix: str = Field(default="ab_test:", description="A/B测试Redis键前缀")
    assignment_expiry: int = Field(default=86400, description="A/B测试分配过期时间（秒）")


class BatchConfig(BaseModel):
    """批处理配置

    定义批处理大小和最大工作线程数。

    - batch_size: 批处理大小
    - max_workers: 最大工作线程数
    """

    batch_size: int = Field(default=100, description="批处理大小")
    max_workers: int = Field(default=10, description="最大工作线程数")


class DatabaseConfig(BaseModel):
    """数据库配置

    定义PostgreSQL连接URL、连接池大小、超时等配置。

    - url: PostgreSQL数据库连接URL（不包含密码，生产环境通过环境变量注入）
    - readonly_url: 只读数据库连接URL（可选）
    - pool_size: 数据库连接池大小
    - max_overflow: 数据库连接池最大溢出数
    - pool_timeout: 数据库连接池超时时间（秒）
    - pool_recycle: 数据库连接回收时间（秒）
    - echo: 是否打印SQL语句
    """

    url: str = Field(
        default="postgresql://localhost:5432/postgres",
        description="PostgreSQL数据库连接URL（不包含密码，通过环境变量注入）"
    )
    readonly_url: Optional[str] = Field(default=None, description="只读数据库连接URL（可选）")
    pool_size: int = Field(default=20, description="数据库连接池大小")
    max_overflow: int = Field(default=40, description="数据库连接池最大溢出数")
    pool_timeout: int = Field(default=30, description="数据库连接池超时时间（秒）")
    pool_recycle: int = Field(default=3600, description="数据库连接回收时间（秒）")
    echo: bool = Field(default=False, description="是否打印SQL语句")


class RedisConfig(BaseModel):
    """Redis配置

    定义Redis连接URL、连接池等配置。
    密码可以通过 URL 中的 user:pass 格式传递。

    - url: Redis连接URL（支持密码内嵌）
    - max_connections: Redis最大连接数
    - socket_timeout: Redis套接字超时（秒）
    """

    url: str = Field(default="redis://localhost:6379/0", description="Redis连接URL（支持密码内嵌）")
    max_connections: int = Field(default=50, description="Redis最大连接数")
    socket_timeout: int = Field(default=5, description="Redis套接字超时（秒）")


class AuthConfig(BaseModel):
    """认证授权配置

    定义API密钥认证和JWT认证的配置。

    - api_key_enabled: 是否启用API密钥认证
    - api_key_header: API密钥头字段
    - jwt_secret_key: JWT密钥
    - jwt_algorithm: JWT算法
    - jwt_expire_minutes: JWT访问令牌过期时间（分钟）
    """

    api_key_enabled: bool = Field(default=True, description="是否启用API密钥认证")
    api_key_header: str = Field(default="X-API-Key", description="API密钥头字段")
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production", description="JWT密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT算法")
    jwt_expire_minutes: int = Field(default=30, description="JWT访问令牌过期时间（分钟）")


class MonitoringConfig(BaseModel):
    """监控配置

    定义Prometheus监控指标的启用状态和端口。

    - enabled: 是否启用监控指标
    - prometheus_port: Prometheus指标端口
    - path: 指标路径
    """

    enabled: bool = Field(default=True, description="是否启用监控指标")
    prometheus_port: int = Field(default=9090, description="Prometheus指标端口")
    path: str = Field(default="/metrics", description="指标路径")


class AlertConfig(BaseModel):
    """告警配置

    定义告警的启用状态、Webhook URL和告警条件。

    - enabled: 是否启用告警
    - webhook_url: 告警Webhook URL
    - on_error: 错误时是否告警
    - on_model_degradation: 模型性能下降时是否告警
    """

    enabled: bool = Field(default=False, description="是否启用告警")
    webhook_url: Optional[str] = Field(default=None, description="告警Webhook URL")
    on_error: bool = Field(default=True, description="错误时是否告警")
    on_model_degradation: bool = Field(default=True, description="模型性能下降时是否告警")


class Settings(BaseSettings):
    """根配置

    聚合所有子配置，作为配置的顶层入口。
    只有根配置继承 BaseSettings，负责环境变量解析。

    - app: 应用基础配置
    - model: 模型存储配置
    - inference: 模型推理配置
    - feature_store: 特征存储配置
    - ab_test: A/B测试配置
    - batch: 批处理配置
    - database: 数据库配置
    - redis: Redis配置
    - storage: 存储配置
    - auth: 认证授权配置
    - monitoring: 监控配置
    - alert: 告警配置
    - logging: 日志配置
    - scorecard: 评分卡默认配置
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="DATAMIND_",
        env_nested_delimiter="_",
    )

    # 基础配置
    app: AppConfig = Field(default_factory=AppConfig, description="应用基础配置")

    # 模型相关配置
    model: ModelConfig = Field(default_factory=ModelConfig, description="模型存储配置")
    inference: InferenceConfig = Field(default_factory=InferenceConfig, description="模型推理配置")
    feature_store: FeatureStoreConfig = Field(default_factory=FeatureStoreConfig, description="特征存储配置")

    # A/B测试和批处理配置
    ab_test: ABTestConfig = Field(default_factory=ABTestConfig, description="A/B测试配置")
    batch: BatchConfig = Field(default_factory=BatchConfig, description="批处理配置")

    # 数据存储配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="数据库配置")
    redis: RedisConfig = Field(default_factory=RedisConfig, description="Redis配置")
    storage: StorageConfig = Field(default_factory=lambda: StorageConfig.from_env(), description="存储配置")

    # 认证配置
    auth: AuthConfig = Field(default_factory=AuthConfig, description="认证授权配置")

    # 监控和告警配置
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig, description="监控配置")
    alert: AlertConfig = Field(default_factory=AlertConfig, description="告警配置")

    # 日志配置
    logging: LoggingConfig = Field(default_factory=lambda: LoggingConfig.from_env(), description="日志配置")

    # 评分卡配置
    scorecard: ScorecardDefaultConfig = Field(default_factory=lambda: ScorecardDefaultConfig.from_env(), description="评分卡默认配置")

    @model_validator(mode='after')
    def _validate_production_settings(self):
        """生产环境安全验证

        验证生产环境下的安全配置：
          - JWT 密钥不能使用默认值
          - 数据库不能使用默认连接字符串
          - 日志级别不能低于 INFO

        返回:
            验证后的配置实例

        抛出:
            ValueError: 安全配置不满足要求
        """
        if self.is_production:
            if self.auth.jwt_secret_key == "your-secret-key-change-in-production":
                raise ValueError("生产环境必须修改 JWT_SECRET_KEY")

            if "localhost" in self.database.url:
                raise ValueError("生产环境不得使用 localhost 数据库地址")

            if self.logging.level < logging.INFO:
                raise ValueError("生产环境日志级别不能低于 INFO")

        return self

    # ==================== 辅助属性 ====================

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.app.environment == Environment.TESTING

    @property
    def is_staging(self) -> bool:
        """是否为预发布环境"""
        return self.app.environment == Environment.STAGING


__all__ = [
    "Settings",
    "Environment",
    "AppConfig",
    "ModelConfig",
    "InferenceConfig",
    "FeatureStoreConfig",
    "ABTestConfig",
    "BatchConfig",
    "DatabaseConfig",
    "RedisConfig",
    "AuthConfig",
    "MonitoringConfig",
    "AlertConfig",
]