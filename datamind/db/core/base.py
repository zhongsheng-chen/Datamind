# datamind/db/core/base.py

"""数据库基类

定义 SQLAlchemy 的声明式基类。
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()