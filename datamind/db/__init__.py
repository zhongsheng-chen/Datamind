# datamind/db/__init__.py

"""数据库模块

提供数据库引擎管理、连接检查和迁移执行能力。

核心功能：
  - get_engine: 获取数据库引擎实例
  - create_engine: 创建异步数据库引擎
  - get_db_url: 获取数据库连接 URL
  - health_check: 检查数据库健康状态
  - run_migrations: 执行数据库迁移

使用示例：
  from datamind.db import get_engine, health_check, run_migrations

  engine = get_engine()
  await health_check()
  run_migrations()
"""

import datamind.db.models
from datamind.db.core.url import get_db_url
from datamind.db.core.engine import get_engine, create_engine
from datamind.db.health import health_check
from datamind.db.migration import run_migrations

__all__ = [
    "get_engine",
    "create_engine",
    "get_db_url",
    "health_check",
    "run_migrations",
]