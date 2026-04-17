# datamind/config/settings.py

"""配置总入口

聚合所有子配置，提供统一的配置访问接口。

属性：
  - database: 数据库配置
  - storage: 存储配置
  - logging: 日志配置
  - ab_test: AB测试配置
  - scorecard: 评分卡配置
  - classification: 分类模型配置
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from datamind.config.database import DatabaseConfig
from datamind.config.storage import StorageConfig
from datamind.config.logging import LoggingConfig
from datamind.config.model import ModelConfig
from datamind.config.ab_test import ABTestConfig
from datamind.config.scorecard import ScorecardConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.service import ServiceConfig


class Settings(BaseSettings):
    """配置总入口类"""

    database: DatabaseConfig = DatabaseConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()
    model: ModelConfig = ModelConfig()
    ab_test: ABTestConfig = ABTestConfig()
    scorecard: ScorecardConfig = ScorecardConfig()
    classification: ClassificationConfig = ClassificationConfig()
    service: ServiceConfig = ServiceConfig()

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()