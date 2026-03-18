# Datamind/datamind/core/db/base.py
"""数据库基础配置"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

# 推荐设置命名约定，使索引和约束的名称更规范
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

Base = declarative_base(metadata=metadata)