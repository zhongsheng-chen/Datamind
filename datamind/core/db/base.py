# Datamind/datamind/core/db/base.py

"""数据库基础配置

提供 SQLAlchemy 的基础配置，包括：
  - 命名约定（naming_convention）：规范索引、约束等对象的命名
  - 声明式基类（Base）：所有数据库模型的基础类
  - 枚举值函数：用于 SQLEnum 的 values_callable

命名约定（naming_convention）：
  使用 SQLAlchemy 推荐的命名约定，确保生成的约束名称格式统一：
    - 索引（index）: ix_%(column_0_label)s
    - 唯一约束（unique）: uq_%(table_name)s_%(column_0_name)s
    - 检查约束（check）: ck_%(table_name)s_%(constraint_name)s
    - 外键约束（foreign key）: fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
    - 主键约束（primary key）: pk_%(table_name)s

这些命名约定使得：
  - 迁移脚本中的约束名称可预测
  - 避免迁移时产生随机名称
  - 便于在数据库级别直接操作和管理

使用方式：
  - 导入 Base 基类
  - 定义模型类继承 Base
  - 定义表名和字段

示例：
    from datamind.core.db.base import Base
    from sqlalchemy import Column, String, Integer

    class MyModel(Base):
        __tablename__ = 'my_table'
        id = Column(Integer, primary_key=True)
        name = Column(String(100), unique=True)  # 自动生成唯一约束名称
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData


def enum_values(enum_cls):
    """
    获取枚举的所有值，用于 SQLEnum 的 values_callable

    参数:
        enum_cls: 枚举类

    返回:
        枚举值的列表

    示例:
        from datamind.core.domain.enums import TaskType
        values = enum_values(TaskType)  # ['scoring', 'fraud_detection']
    """
    return [e.value for e in enum_cls]


metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

Base = declarative_base(metadata=metadata)