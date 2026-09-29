"""配置模块.

提供统一的配置访问接口。

核心功能：
  - Settings: 聚合全部子配置
  - get_settings: 获取缓存的全局配置实例
  - get_xxx_config: 按配置域加载独立配置

使用示例：
  from datamind.config import (
      get_service_config,
      get_settings,
  )

  settings = get_settings()
  service_config = get_service_config()

  print(settings.service.environment)
  print(settings.database.url)
  print(settings.storage.type)
  print(service_config.port)
"""

from datamind.config.settings import (
    Settings,
    get_settings,
)
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


__all__ = [
    "Settings",
    "get_audit_config",
    "get_auth_config",
    "get_classification_config",
    "get_console_config",
    "get_database_config",
    "get_initialization_config",
    "get_logging_config",
    "get_runtime_config",
    "get_scoring_config",
    "get_service_config",
    "get_settings",
    "get_storage_config",
    "get_task_queue_config",
    "get_task_worker_config",
]
