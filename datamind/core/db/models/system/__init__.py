# Datamind/datamind/core/db/models/system/__init__.py

"""系统相关数据库模型

包含系统配置、运行时参数等系统级功能的数据模型。

模块组成：
  - config: 系统配置表定义（SystemConfig）
"""

from .config import SystemConfig

__all__ = [
    'SystemConfig',
]