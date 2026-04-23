# datamind/db/init.py

"""数据库初始化

负责：
- 初始化数据库连接
- 创建所有数据表

核心功能：
  - init_db: 初始化数据库（创建所有表）
  - check_db_connection: 检查数据库连接
  - create_tables: 创建表
  - drop_tables: 删除表（危险）
  - reset_database: 重建数据库（危险）
"""

from sqlalchemy import text

from datamind.db.core import Base, get_engine
from datamind.config.database import DatabaseConfig


def init_db(config: DatabaseConfig = None, recreate: bool = False):
    """初始化数据库

    参数：
        config: 数据库配置对象
        recreate: 是否重新创建表（危险，会删除所有数据）

    异常：
        初始化失败时抛出异常
    """
    engine = get_engine(config)

    if recreate:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)


def check_db_connection(config: DatabaseConfig = None) -> bool:
    """检查数据库连接

    参数：
        config: 数据库配置对象

    返回：
        bool: 连接是否正常
    """
    try:
        engine = get_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False


def create_tables(config: DatabaseConfig = None):
    """创建表（不删除已有表）

    参数：
        config: 数据库配置对象
    """
    engine = get_engine(config)
    Base.metadata.create_all(bind=engine)


def drop_tables(config: DatabaseConfig = None):
    """删除所有表（危险操作）

    参数：
        config: 数据库配置对象
    """
    engine = get_engine(config)
    Base.metadata.drop_all(bind=engine)


def reset_database(config: DatabaseConfig = None):
    """重建数据库（危险操作，会删除所有数据）

    参数：
        config: 数据库配置对象
    """
    drop_tables(config)
    create_tables(config)