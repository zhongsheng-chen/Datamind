"""数据库引擎管理.

提供异步数据库引擎的创建、单例获取和资源释放能力。

核心功能：
  - create_engine: 创建异步数据库引擎
  - get_engine: 获取数据库引擎单例
  - dispose_engine: 关闭数据库引擎并重置会话工厂

使用示例：
  from datamind.db.core.engine import (
      dispose_engine,
      get_engine,
  )

  engine = get_engine()

  # 使用引擎...

  await dispose_engine()
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from datamind.config import get_database_config


_engine: AsyncEngine | None = None


def create_engine() -> AsyncEngine:
    """创建异步数据库引擎.

    返回：
        AsyncEngine 实例
    """
    db = get_database_config()

    return create_async_engine(
        db.url,
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


def get_engine() -> AsyncEngine:
    """获取数据库引擎单例.

    首次调用时创建引擎，后续调用返回同一实例。

    返回：
        AsyncEngine 实例
    """
    global _engine

    engine = _engine

    if engine is None:
        engine = create_engine()
        _engine = engine

    return engine


async def dispose_engine() -> None:
    """关闭数据库引擎并重置会话工厂.

    解除全局引擎和 SessionFactory 对旧引擎的引用，
    然后释放原连接池资源。
    """
    global _engine

    from datamind.db.core.session import (
        reset_session_factory,
    )

    engine = _engine

    _engine = None
    reset_session_factory()

    if engine is not None:
        await engine.dispose()
