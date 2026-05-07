# datamind/db/reader/base_reader.py

"""读取器基类

提供数据库读取能力，会话由 session_scope 统一管理。

核心功能：
  - session: 数据库会话

使用示例：
  from datamind.db.reader.base_reader import BaseReader

  class MetadataReader(BaseReader):

      async def get_model(self, model_id: str):
          stmt = select(Metadata).where(
              Metadata.model_id == model_id
          )

          result = await self.session.execute(stmt)
          return result.scalar_one_or_none()
"""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseReader:
    """读取器基类

    属性：
        session: 数据库会话（AsyncSession）
    """

    def __init__(self, session: AsyncSession):
        """
        初始化读取器

        参数：
            session: 异步数据库会话对象，用于执行查询
        """
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        return self._session