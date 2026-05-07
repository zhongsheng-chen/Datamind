# datamind/db/core/mixins.py

"""模型混入类

提供通用的模型字段和功能。

核心功能：
  - IdMixin: 自增主键
  - TimestampMixin: 创建时间和更新时间
"""

from sqlalchemy import Column, DateTime, BigInteger
from sqlalchemy.sql import func


class IdMixin:
    """自增主键混入类"""

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="自增主键 ID"
    )


class TimestampMixin:
    """时间戳混入类"""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )