# datamind/db/core/session.py

"""数据库会话管理

提供异步会话的创建和上下文管理。

核心功能：
  - session_scope: 会话作用域上下文管理器

使用示例：
  from datamind.db.session import session_scope

  async with session_scope() as session:
      result = await session.execute(...)
"""

from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datamind.db.core.engine import get_engine


_SessionFactory: Optional[async_sessionmaker[AsyncSession]] = None

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 SessionFactory（单例延迟初始化）"""
    global _SessionFactory

    if _SessionFactory is None:
        engine = get_engine()

        if engine is None:
            raise RuntimeError("数据库 engine 未初始化")

        _SessionFactory = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _SessionFactory



@asynccontextmanager
async def session_scope():
    """会话作用域上下文管理器

    自动管理会话生命周期，提交事务或回滚异常。

    使用示例：
        async with session_scope() as session:
            result = await session.execute(...)
    """
    SessionFactory = get_session_factory()
    session: AsyncSession = SessionFactory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()