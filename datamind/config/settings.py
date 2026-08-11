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
  print(settings.console.port)
  print(settings.initialization.admin_username)
  print(settings.runtime.shadow_enabled)
  print(settings.database.url)
  print(settings.storage.type)
"""

from functools import lru_cache

from datamind.config.audit import AuditConfig
from datamind.config.auth import AuthConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.console import ConsoleConfig
from datamind.config.database import DatabaseConfig
from datamind.config.initialization import InitializationConfig
from datamind.config.logging import LoggingConfig
from datamind.config.runtime import RuntimeConfig
from datamind.config.scorecard import ScorecardConfig
from datamind.config.storage import StorageConfig
from datamind.config.service import ServiceConfig


class Settings:
    """配置总入口类"""

    audit: AuditConfig
    auth: AuthConfig
    classification: ClassificationConfig
    console: ConsoleConfig
    database: DatabaseConfig
    initialization: InitializationConfig
    logging: LoggingConfig
    runtime: RuntimeConfig
    scorecard: ScorecardConfig
    storage: StorageConfig
    service: ServiceConfig

    def __init__(self) -> None:
        self.audit = AuditConfig()
        self.auth = AuthConfig()
        self.classification = ClassificationConfig()
        self.console = ConsoleConfig()
        self.database = DatabaseConfig()
        self.initialization = InitializationConfig()
        self.logging = LoggingConfig()
        self.runtime = RuntimeConfig()
        self.scorecard = ScorecardConfig()
        self.storage = StorageConfig()
        self.service = ServiceConfig(**{})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取缓存的全局配置实例

    返回：
        缓存的 Settings 实例
    """
    return Settings()
