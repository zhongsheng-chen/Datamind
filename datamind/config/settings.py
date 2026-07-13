# datamind/config/settings.py

"""配置总入口

聚合所有子配置，提供统一的配置访问接口和缓存实例。

核心功能：
  - Settings: 聚合并初始化所有子配置
  - get_settings: 获取缓存的全局配置实例

使用示例：
  from datamind.config import get_settings

  settings = get_settings()

  print(settings.service.environment)
  print(settings.database.url)
  print(settings.storage.type)
"""

from functools import lru_cache

from datamind.config.audit import AuditConfig
from datamind.config.auth import AuthConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.database import DatabaseConfig
from datamind.config.logging import LoggingConfig
from datamind.config.scorecard import ScorecardConfig
from datamind.config.service import ServiceConfig
from datamind.config.storage import StorageConfig


class Settings:
    """配置总入口类"""

    database: DatabaseConfig
    storage: StorageConfig
    logging: LoggingConfig
    audit: AuditConfig
    auth: AuthConfig
    scorecard: ScorecardConfig
    classification: ClassificationConfig
    service: ServiceConfig

    def __init__(self) -> None:
        self.database = DatabaseConfig()
        self.storage = StorageConfig()
        self.logging = LoggingConfig()
        self.audit = AuditConfig()
        self.auth = AuthConfig()
        self.scorecard = ScorecardConfig()
        self.classification = ClassificationConfig()
        self.service = ServiceConfig(**{})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取缓存的全局配置实例

    返回：
        缓存的 Settings 实例
    """
    return Settings()
