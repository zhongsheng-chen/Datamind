# datamind/db/core/__init__.py

"""数据库核心模块

提供声明式基类、模型混入类和会话管理。

核心功能：
  - Base: SQLAlchemy 声明式基类
  - IdMixin: 自增主键混入类
  - TimestampMixin: 时间戳混入类
  - session_scope: 会话作用域上下文管理器

使用示例：
  # 模型定义
  from datamind.db.core import Base, IdMixin, TimestampMixin

  class MyModel(Base, IdMixin, TimestampMixin):
      __tablename__ = "my_table"
      name = Column(String(100))

  # 会话管理
  from datamind.db.core import session_scope

  async with session_scope() as session:
      result = await session.execute(...)
"""

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin
from datamind.db.core.session import session_scope

__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    "session_scope",
]