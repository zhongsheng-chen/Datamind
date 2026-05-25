# datamind/db/__init__.py

"""数据库模块

提供数据库引擎管理、连接检查和迁移执行能力。

核心功能：
  - get_engine: 获取数据库引擎实例
  - create_engine: 创建异步数据库引擎
  - get_db_url: 获取数据库连接 URL

使用示例：
  from datamind.db import get_engine

  engine = get_engine()
"""

import datamind.db.models
from datamind.db.core.url import get_db_url
from datamind.db.core.engine import get_engine, create_engine

__all__ = [
    "get_engine",
    "create_engine",
    "get_db_url",
]