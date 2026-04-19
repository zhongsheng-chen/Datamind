# datamind/config/__init__.py

"""配置模块

提供统一的配置访问接口。

使用示例：
  from datamind.config import get_settings

  settings = get_settings()
  print(settings.service.environment)
  print(settings.database.host)
  print(settings.storage.storage_type)
"""

from datamind.config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]