# datamind/db/core/uow.py

"""工作单元

统一事务管理器，确保一个请求中的所有数据库操作
在同一个事务中完成。

核心功能：
  - UnitOfWork: 工作单元，管理事务生命周期

使用示例：
  from datamind.db.core.uow import UnitOfWork
  from datamind.db.writers import MetadataWriter

  async with UnitOfWork() as uow:
      writer = MetadataWriter(uow.session)
      await writer.create(...)
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.core.session import get_session_factory


class UnitOfWork:
    """工作单元

    属性：
        session: 当前数据库会话（AsyncSession）
    """

    def __init__(self):
        """初始化工作单元"""
        self._session: Optional[AsyncSession] = None

    @property
    def session(self) -> AsyncSession:
        """获取当前会话"""
        if self._session is None:
            raise RuntimeError("工作单元未初始化，请在 async with UnitOfWork() 上下文中使用")

        return self._session

    async def __aenter__(self):
        """进入事务上下文"""
        session_factory = get_session_factory()
        self._session = session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出事务上下文"""

        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()

        finally:
            await self.close()
            self._session = None

        return False

    async def close(self):
        """关闭会话"""
        await self._session.close()