# datamind/db/core/uow.py

"""工作单元

统一事务管理器，确保一个请求中的所有数据库操作
在同一个事务中完成。

核心功能：
  - UnitOfWork: 工作单元，管理事务生命周期

使用示例：
  from datamind.db.core.uow import UnitOfWork
  from datamind.db.repositories import MetadataRepository

  async with UnitOfWork() as uow:
      repo = MetadataRepository(uow.session)
      await repo.create_model(...)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.core.session import get_session_factory


class UnitOfWork:
    """工作单元

    属性：
        session: 当前数据库会话（AsyncSession）
    """

    def __init__(self):
        """初始化工作单元"""
        self._session: AsyncSession | None = None
        self._rollback_only: bool = False

    @property
    def session(self) -> AsyncSession:
        """获取当前会话"""
        if self._session is None:
            raise RuntimeError("工作单元未初始化，请在 async with UnitOfWork() 上下文中使用")

        return self._session

    def mark_rollback(self) -> None:
        """标记事务必须回滚"""
        self._rollback_only = True

    async def __aenter__(self) -> "UnitOfWork":
        """进入事务上下文"""
        self._rollback_only = False

        SessionFactory = get_session_factory()
        self._session = SessionFactory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出事务上下文"""
        session = self.session

        try:
            if exc_type is not None or self._rollback_only:
                await session.rollback()
            else:
                await session.commit()

        finally:
            await self.close()
            self._session = None

        return False

    async def close(self) -> None:
        """关闭会话"""
        if self._session is not None:
            await self._session.close()