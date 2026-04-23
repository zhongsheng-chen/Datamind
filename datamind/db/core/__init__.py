# datamind/db/core/__init__.py

"""数据库核心模块

提供数据库引擎、会话管理和基础模型类。

核心功能：
  - Base: SQLAlchemy 声明式基类
  - IdMixin: 自增主键混入类
  - TimestampMixin: 时间戳混入类
  - get_engine: 获取数据库引擎
  - init_engine: 初始化数据库引擎
  - SessionManager: 会话管理器
  - get_session_manager: 获取全局会话管理器
  - get_session: 获取数据库会话
  - session_scope: 会话上下文管理器

使用示例：
  from datamind.db.core import Base, IdMixin, TimestampMixin
  from datamind.db.core import get_engine, get_session, session_scope

  # 初始化引擎
  engine = get_engine(config)

  # 获取会话
  session = get_session()

  # 使用上下文管理器
  with session_scope() as session:
      session.query(Model).all()
"""

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin
from datamind.db.core.engine import get_engine, init_engine
from datamind.db.core.session import (
    SessionManager,
    get_session_manager,
    get_session,
    session_scope,
)

__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    "get_engine",
    "init_engine",
    "SessionManager",
    "get_session_manager",
    "get_session",
    "session_scope",
]