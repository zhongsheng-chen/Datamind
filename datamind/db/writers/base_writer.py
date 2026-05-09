# datamind/db/writer/base_writer.py

"""写入器基类

提供数据库写入接口，事务由 session_scope 统一管理。

核心功能：
  - add: 添加单个对象
  - add_all: 添加多个对象
  - delete: 删除对象
  - flush: 刷新会话，将待处理操作发送到数据库
  - refresh: 刷新对象状态

使用示例：
  from datamind.db.writer.base_writer import BaseWriter

  class MetadataWriter(BaseWriter):
      async def create(self, name: str):
          metadata = Metadata(name=name)

          self.add(metadata)
          await self.flush()

          return metadata
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class BaseWriter:
    """写入器基类

    属性：
        session: 数据库会话（AsyncSession）
    """

    def __init__(self, session: AsyncSession):
        """
        初始化写入器

        参数：
            session: 异步数据库会话对象，用于执行数据库操作
        """
        self._session = session

    def add(self, obj: Any) -> None:
        """添加单个对象"""
        self._session.add(obj)

    def add_all(self, objs: Iterable[Any]) -> None:
        """添加多个对象"""
        self._session.add_all(objs)

    async def delete(self, obj: Any) -> None:
        """删除对象"""
        await self._session.delete(obj)

    async def flush(self) -> None:
        """刷新会话"""
        await self._session.flush()

    async def refresh(self, obj: Any) -> None:
        """刷新对象状态"""
        await self._session.refresh(obj)