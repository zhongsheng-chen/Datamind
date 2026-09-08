"""数据库核心模块

提供声明式基类、通用混入类、工作单元、
数据库引擎、会话工厂和连接 URL 管理能力。

核心功能：
  - Base: SQLAlchemy 声明式基类
  - IdMixin: 自增主键混入类
  - TimestampMixin: 时间戳混入类
  - UnitOfWork: 工作单元
  - create_engine: 创建数据库引擎
  - get_engine: 获取数据库引擎单例
  - dispose_engine: 关闭数据库引擎
  - get_session_factory: 获取会话工厂单例
  - reset_session_factory: 重置会话工厂
  - get_db_url: 获取数据库连接 URL

使用示例：
  from datamind.db.core import (
      Base,
      IdMixin,
      TimestampMixin,
      UnitOfWork,
  )

  class User(
      IdMixin,
      TimestampMixin,
      Base,
  ):
      __tablename__ = "users"

  async def main() -> None:
      async with UnitOfWork() as uow:
          session = uow.session

          # 数据库仓储操作
          ...
"""

from datamind.db.core.base import Base
from datamind.db.core.engine import (
    create_engine,
    dispose_engine,
    get_engine,
)
from datamind.db.core.mixins import (
    IdMixin,
    TimestampMixin,
)
from datamind.db.core.session import (
    get_session_factory,
    reset_session_factory,
)
from datamind.db.core.uow import UnitOfWork
from datamind.db.core.url import get_db_url


__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    "UnitOfWork",
    "create_engine",
    "get_engine",
    "dispose_engine",
    "get_session_factory",
    "reset_session_factory",
    "get_db_url",
]
