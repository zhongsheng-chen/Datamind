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
from datamind.config.providers import (
    get_audit_config,
    get_auth_config,
    get_classification_config,
    get_console_config,
    get_database_config,
    get_initialization_config,
    get_logging_config,
    get_runtime_config,
    get_scoring_config,
    get_service_config,
    get_storage_config,
    get_task_queue_config,
    get_task_worker_config,
)
from datamind.config.queue import TaskQueueConfig
from datamind.config.runtime import RuntimeConfig
from datamind.config.scoring import ScoringConfig
from datamind.config.service import ServiceConfig
from datamind.config.storage import StorageConfig
from datamind.config.worker import TaskWorkerConfig


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
    scoring: ScoringConfig
    storage: StorageConfig
    service: ServiceConfig
    task_queue: TaskQueueConfig
    task_worker: TaskWorkerConfig

    def __init__(self) -> None:
        self.audit = get_audit_config()
        self.auth = get_auth_config()
        self.classification = get_classification_config()
        self.console = get_console_config()
        self.database = get_database_config()
        self.initialization = get_initialization_config()
        self.logging = get_logging_config()
        self.runtime = get_runtime_config()
        self.scoring = get_scoring_config()
        self.storage = get_storage_config()
        self.service = get_service_config()
        self.task_queue = get_task_queue_config()
        self.task_worker = get_task_worker_config()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取缓存的全局配置实例

    返回：
        缓存的 Settings 实例
    """
    return Settings()
