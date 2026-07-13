# datamind/db/core/mixins.py

"""数据库模型混入类

提供数据库模型通用的主键和时间戳字段。

核心功能：
  - IdMixin: 提供自增主键
  - TimestampMixin: 提供创建时间和更新时间

注意：
  - 时间字段使用带时区的数据库类型
  - updated_at 在 SQLAlchemy 执行更新语句时自动设置为数据库当前时间

使用示例：
  from sqlalchemy import Column, String

  from datamind.db.core.base import Base
  from datamind.db.core.mixins import (
      IdMixin,
      TimestampMixin,
  )

  class User(
      IdMixin,
      TimestampMixin,
      Base,
  ):
      __tablename__ = "users"

      name = Column(
          String(100),
          nullable=False,
      )
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
)
from sqlalchemy.sql import func


class IdMixin:
    """自增主键混入类"""

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="自增主键 ID",
    )


class TimestampMixin:
    """时间戳混入类"""

    created_at = Column(
        DateTime(
            timezone=True
        ),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at = Column(
        DateTime(
            timezone=True
        ),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
