# datamind/db/core/mixins.py

"""模型混入类

提供通用的模型字段和功能。

核心功能：
  - IdMixin: 自增主键
  - TimestampMixin: 创建时间和更新时间
"""

from sqlalchemy import Column, DateTime, BigInteger, Identity
from sqlalchemy.sql import func


class IdMixin:
    """自增主键混入类"""

    id = Column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    """时间戳混入类

    属性：
        created_at: 创建时间
        updated_at: 更新时间
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)