# datamind/db/core/session.py

"""数据库会话管理

提供异步 SessionFactory，用于 UnitOfWork 创建会话。

核心功能：
  - get_session_factory: 获取 SessionFactory，返回单例
  - reset_session_factory: 重置 SessionFactory，通常用于测试

使用示例：
  from datamind.db.core.session import get_session_factory

  SessionFactory = get_session_factory()
  async with SessionFactory() as session:
      result = await session.execute(...)
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datamind.db.core.engine import get_engine


_SessionFactory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 SessionFactory

    返回：
        async_sessionmaker 实例
    """
    global _SessionFactory

    if _SessionFactory is None:
        _SessionFactory = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )

    return _SessionFactory


def reset_session_factory() -> None:
    """重置 SessionFactory

    通常在测试用例的 teardown 中调用。
    """
    global _SessionFactory
    _SessionFactory = None