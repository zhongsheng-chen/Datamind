# datamind/db/writer/base_writer.py

"""写入器基类

提供数据库写入接口，事务由 session_scope 统一管理。

核心功能：
  - add: 添加单个对象
  - add_all: 添加多个对象
  - flush: 刷新会话，将待处理操作发送到数据库

使用示例：
  from datamind.db.writer.base_writer import BaseWriter

  class UserWriter(BaseWriter):
      def create(self, name: str):
          user = User(name=name)
          self.add(user)
          return user
"""

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class BaseWriter:
    """写入器基类

    属性：
        session: 数据库会话
    """

    session: AsyncSession

    def add(self, obj):
        """添加单个对象"""
        self.session.add(obj)

    def add_all(self, objs):
        """添加多个对象"""
        self.session.add_all(objs)

    async def flush(self):
        """刷新会话"""
        await self.session.flush()