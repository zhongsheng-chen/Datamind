# datamind/db/reader/base_reader.py

"""读取器基类

提供数据库读取能力，会话由 session_scope 统一管理。

核心功能：
  - session: 数据库会话

使用示例：
  from datamind.db.reader.base_reader import BaseReader

  class MetadataReader(BaseReader):

      async def get_by_model_id(self, model_id: str):
          stmt = select(Metadata).where(
              Metadata.model_id == model_id
          )

          result = await self.session.execute(stmt)
          return result.scalar_one_or_none()
"""

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class BaseReader:
    """读取器基类

    属性：
        session: 数据库会话
    """

    session: AsyncSession