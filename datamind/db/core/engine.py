# datamind/db/core/engine.py

"""数据库引擎管理

提供数据库引擎的单例管理和连接池配置。

核心功能：
  - get_engine: 获取数据库引擎实例（单例）
  - init_engine: 初始化数据库引擎（重置单例）
"""

from sqlalchemy import create_engine
from datamind.config.database import DatabaseConfig

_engine = None


def get_engine(config: DatabaseConfig = None):
    """获取数据库引擎实例（单例）

    参数：
        config: 数据库配置对象

    返回：
        SQLAlchemy 引擎实例
    """
    global _engine
    if _engine is None:
        if config is None:
            from datamind.config import get_settings
            config = get_settings().database

        db_url = f"postgresql+psycopg2://{config.user}:{config.password}@{config.host}:{config.port}/{config.database}"

        _engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
            echo=False,
            isolation_level="READ COMMITTED",
        )
    return _engine


def init_engine(config: DatabaseConfig = None):
    """初始化数据库引擎（重置单例）

    参数：
        config: 数据库配置对象
    """
    global _engine
    _engine = None
    return get_engine(config)