"""配置模块

提供统一的配置访问接口。

核心功能：
  - Settings: 聚合全部子配置
  - get_settings: 获取缓存的全局配置实例

使用示例：
  from datamind.config import get_settings

  settings = get_settings()

  print(settings.service.environment)
  print(settings.database.url)
  print(settings.storage.type)
"""

from datamind.config.settings import (
    Settings,
    get_settings,
)


__all__ = [
    "Settings",
    "get_settings",
]
