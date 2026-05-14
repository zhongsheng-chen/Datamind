# datamind/db/repositories/base.py

"""数据库访问基类

提供统一的数据访问能力，由 UnitOfWork 统一管理事务。

核心功能：
  - add: 添加单个对象
  - add_all: 添加多个对象
  - delete: 删除对象
  - flush: 刷新会话，将待处理操作发送到数据库
  - refresh: 刷新对象状态

使用示例：
  from datamind.db.repositories.base import BaseRepository
  from datamind.db.core.uow import UnitOfWork

  async with UnitOfWork() as uow:
      repo = BaseRepository(uow.session)

      repo.add(obj)
      await repo.flush()
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """数据库访问基类

    属性：
        session: 数据库会话对象
    """

    def __init__(self, session: AsyncSession):
        """
        初始化数据库访问基类

        参数：
            session: 异步数据库会话对象，用于执行数据库操作
        """
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        return self._session

    def add(self, obj: Any) -> None:
        """添加单个对象"""
        self._session.add(obj)

    def add_all(self, objs: Iterable[Any]) -> None:
        """添加多个对象"""
        self._session.add_all(objs)

    def delete(self, obj: Any) -> None:
        """删除对象"""
        self._session.delete(obj)

    async def flush(self) -> None:
        """刷新会话，将待处理操作发送到数据库"""
        await self._session.flush()

    async def refresh(self, obj: Any) -> None:
        """刷新对象状态"""
        await self._session.refresh(obj)