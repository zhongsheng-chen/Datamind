# datamind/db/writer/base_writer.py

"""写入器基类

提供统一的数据库写入接口，事务由 UnitOfWork 统一管理。

注意：
  - Writer 只负责 add()，不负责 flush/commit
  - 事务控制由 UnitOfWork 统一管理
"""

from dataclasses import dataclass
from sqlalchemy.orm import Session


@dataclass
class BaseWriter:
    """写入器基类

    属性：
        session: 数据库会话
    """

    session: Session

    def add(self, obj):
        """添加单个对象"""
        self.session.add(obj)

    def add_all(self, objs):
        """添加多个对象"""
        self.session.add_all(objs)