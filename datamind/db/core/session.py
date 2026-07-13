# datamind/db/core/session.py

"""数据库会话管理

提供异步 SessionFactory，用于 UnitOfWork 创建数据库会话。

核心功能：
  - get_session_factory: 获取会话工厂单例
  - reset_session_factory: 重置会话工厂

使用示例：
  from sqlalchemy import text

  from datamind.db.core.session import get_session_factory

  session_factory = get_session_factory()

  async with session_factory() as session:
      result = await session.execute(
          text("SELECT 1")
      )
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datamind.db.core.engine import get_engine


_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取会话工厂单例

    首次调用时创建会话工厂，后续调用返回同一实例。

    返回：
        async_sessionmaker 实例
    """
    global _session_factory

    session_factory = _session_factory

    if session_factory is None:
        session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
        _session_factory = session_factory

    return session_factory


def reset_session_factory() -> None:
    """重置会话工厂

    仅清除会话工厂单例，不会关闭已经创建的数据库会话。
    通常由 dispose_engine() 或测试清理逻辑调用。
    """
    global _session_factory

    _session_factory = None
