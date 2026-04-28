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

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datamind.db.core.engine import get_engine


SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=get_engine(),
    autoflush=False,
    expire_on_commit=False,
)


@asynccontextmanager
async def session_scope():
    """会话作用域上下文管理器

    自动管理会话生命周期，提交事务或回滚异常。

    使用示例：
        async with session_scope() as session:
            result = await session.execute(...)
    """
    session: AsyncSession = SessionFactory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()