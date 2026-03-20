# Datamind/datamind/core/db/__init__.py

"""数据库模块

提供数据库连接、会话管理、模型定义等功能，是数据持久化层的核心模块。

模块组成：
  - base: SQLAlchemy 基础配置（声明式基类、命名约定）
  - database: 数据库管理器（连接池、会话管理、事务管理、复制监控）
  - models: 数据模型定义（ORM 模型类）

核心功能：
  - 数据库连接池管理（支持主库和只读副本）
  - 会话管理（自动提交/回滚的上下文管理器）
  - 事务管理（支持手动和自动事务）
  - 健康检查（定期检查数据库连接状态）
  - 复制监控（主备复制延迟监控、告警）
  - 模型定义（ORM 模型，支持关联关系）
"""

from datamind.core.db.database import db_manager, get_db, init_db
from datamind.core.db.models import Base
from datamind.core.domain import enums

__all__ = [
    'db_manager',
    'get_db',
    'init_db',
    'Base',
    'enums',
]