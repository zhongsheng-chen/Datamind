# datamind/db/core/engine.py

"""数据库引擎管理

提供异步数据库引擎的创建和单例管理。

核心功能：
  - create_engine: 创建异步数据库引擎
  - get_engine: 获取数据库引擎实例，返回单例
  - dispose_engine: 关闭数据库引擎

使用示例：
  from datamind.db.core.engine import get_engine, dispose_engine

  engine = get_engine()
  # 使用引擎...
  await dispose_engine()
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from datamind.config import get_settings
from datamind.db.core.url import get_db_url

_engine: AsyncEngine | None = None


def create_engine() -> AsyncEngine:
    """创建异步数据库引擎

    返回：
        AsyncEngine 实例
    """
    settings = get_settings()
    db = settings.database
    url = get_db_url()

    engine = create_async_engine(
        url,
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout,
        pool_recycle=db.pool_recycle,
        echo=db.echo,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
        },
    )

    return engine


def get_engine() -> AsyncEngine:
    """获取数据库引擎实例（单例）

    返回：
        AsyncEngine 实例
    """
    global _engine

    if _engine is None:
        _engine = create_engine()

    return _engine


async def dispose_engine() -> None:
    """关闭数据库引擎

    释放连接池资源，通常在应用关闭时调用。
    """
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None