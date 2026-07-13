# datamind/db/__init__.py

"""数据库模块

提供数据库引擎生命周期、连接 URL 和健康检查能力。
导入该模块时会注册全部数据库模型。

核心功能：
  - create_engine: 创建数据库引擎
  - get_engine: 获取数据库引擎单例
  - dispose_engine: 关闭数据库引擎
  - get_db_url: 获取数据库连接 URL
  - health_check: 检查数据库健康状态

使用示例：
  from datamind.db import (
      dispose_engine,
      health_check,
  )

  async def main() -> None:
      result = await health_check()

      print(
          result["status"]
      )

      await dispose_engine()
"""

import datamind.db.models

from datamind.db.core import (
    create_engine,
    dispose_engine,
    get_db_url,
    get_engine,
)
from datamind.db.health import health_check


__all__ = [
    "create_engine",
    "get_engine",
    "dispose_engine",
    "get_db_url",
    "health_check",
]
