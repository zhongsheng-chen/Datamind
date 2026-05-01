# datamind/db/core/uow.py

"""工作单元

统一事务管理器，确保一个请求中的所有数据库操作
在同一个事务中完成。

核心功能：
  - UnitOfWork: 工作单元，管理事务生命周期

使用示例：
  from datamind.db.core.uow import UnitOfWork

  async with UnitOfWork() as uow:
      session = uow.session

      # 执行业务数据库操作
      # await repo.create(...)

      await uow.commit()
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.core.session import get_session_factory


class UnitOfWork:
    """工作单元"""

    def __init__(self):
        self._session: Optional[AsyncSession] = None

    @property
    def session(self) -> AsyncSession:
        """获取当前会话"""
        return self._session

    async def __aenter__(self):
        """进入事务上下文"""
        SessionFactory = get_session_factory()

        self._session = SessionFactory()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出事务上下文"""
        try:
            if exc_type:
                await self.rollback()

        finally:
            await self.close()

    async def commit(self):
        """提交事务"""
        await self._session.commit()

    async def rollback(self):
        """回滚事务"""
        await self._session.rollback()

    async def flush(self):
        """刷新会话"""
        await self._session.flush()

    async def close(self):
        """关闭会话"""
        await self._session.close()