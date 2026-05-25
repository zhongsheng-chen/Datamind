# datamind/db/core/mixins.py

"""模型混入类

提供通用的模型字段和功能。

核心功能：
  - IdMixin: 自增主键
  - TimestampMixin: 创建时间和更新时间
"""

from datetime import datetime
from sqlalchemy import DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class IdMixin:
    """自增主键混入类"""

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="自增主键 ID"
    )


class TimestampMixin:
    """时间戳混入类"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )