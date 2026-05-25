# datamind/db/core/base.py

"""数据库基类

定义 SQLAlchemy 的声明式基类和命名约定。
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 命名约定
naming_convention = {
    "ix": "ix_%(column_0_label)s",                                        # 索引
    "uq": "uq_%(table_name)s_%(column_0_name)s",                          # 唯一约束
    "ck": "ck_%(table_name)s_%(constraint_name)s",                        # 检查约束
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",  # 外键
    "pk": "pk_%(table_name)s"                                             # 主键
}

# 元数据配置
metadata = MetaData(naming_convention=naming_convention)

class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    metadata = metadata