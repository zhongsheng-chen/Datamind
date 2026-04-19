# datamind/config/settings.py

"""配置总入口

聚合所有子配置，提供统一的配置访问接口。

使用示例：
  from datamind.config import get_settings

  settings = get_settings()
  print(settings.service.environment)
  print(settings.database.host)
  print(settings.storage.type)
"""

from functools import lru_cache

from datamind.config.database import DatabaseConfig
from datamind.config.storage import StorageConfig
from datamind.config.logging import LoggingConfig
from datamind.config.audit import AuditConfig
from datamind.config.model import ModelConfig
from datamind.config.ab_test import ABTestConfig
from datamind.config.scorecard import ScorecardConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.service import ServiceConfig


class Settings:
    """配置总入口类"""

    def __init__(self):
        self.database = DatabaseConfig()
        self.storage = StorageConfig()
        self.logging = LoggingConfig()
        self.audit = AuditConfig()
        self.model = ModelConfig()
        self.ab_test = ABTestConfig()
        self.scorecard = ScorecardConfig()
        self.classification = ClassificationConfig()
        self.service = ServiceConfig()


@lru_cache
def get_settings() -> Settings:
    """获取配置单例

    返回：
        全局唯一的 Settings 实例
    """
    return Settings()