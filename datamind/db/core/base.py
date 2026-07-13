# datamind/db/core/base.py

"""数据库基类

定义 SQLAlchemy 声明式基类和数据库对象命名约定。

核心功能：
  - naming_convention: 约束和索引命名约定
  - metadata: 数据库模型共享元数据
  - Base: SQLAlchemy 声明式基类

注意：
  - CheckConstraint 必须显式提供 name
  - Alembic 应使用 Base.metadata 作为 target_metadata

使用示例：
  from sqlalchemy import Column, Integer, String

  from datamind.db.core.base import Base

  class User(Base):
      __tablename__ = "users"

      id = Column(
          Integer,
          primary_key=True,
          autoincrement=True,
      )

      name = Column(
          String(100),
          nullable=False,
      )
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


naming_convention: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(
    naming_convention=naming_convention
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    metadata = metadata
