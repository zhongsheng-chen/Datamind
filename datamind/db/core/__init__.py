# datamind/db/core/__init__.py

"""数据库核心模块

提供声明式基类、混入类、工作单元和引擎管理。

核心功能：
  - Base: SQLAlchemy 声明式基类
  - IdMixin: 自增主键混入类
  - TimestampMixin: 时间戳混入类
  - UnitOfWork: 工作单元
  - get_engine: 获取数据库引擎

使用示例：
  from datamind.db.core import Base, IdMixin, TimestampMixin, UnitOfWork, get_engine

  class MyModel(Base, IdMixin, TimestampMixin):
      __tablename__ = "my_table"
      name = Column(String(100))

  async with UnitOfWork() as uow:
      session = uow.session
      # 执行数据库操作
"""

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin
from datamind.db.core.engine import get_engine
from datamind.db.core.uow import UnitOfWork

__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    "UnitOfWork",
    "get_engine",
]