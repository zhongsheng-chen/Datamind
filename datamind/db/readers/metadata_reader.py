# datamind/db/reader/metadata_reader.py

"""模型元数据读取器

提供模型元数据的查询能力。

核心功能：
  - get_model: 获取模型信息
  - list_active_models: 获取所有活跃模型
  - list_models: 获取模型列表（支持过滤条件）

使用示例：
  from datamind.db.reader.metadata_reader import MetadataReader

  reader = MetadataReader(session)

  model = await reader.get_model("mdl_a1b2c3d4")
  models = await reader.list_active_models()
  models = await reader.list_models(status="active")
"""

from sqlalchemy import select

from datamind.db.models.metadata import Metadata
from datamind.db.readers.base_reader import BaseReader


class MetadataReader(BaseReader):
    """模型元数据读取器"""

    async def get_model(self, model_id: str) -> Metadata | None:
        """获取模型信息

        参数：
            model_id: 模型唯一标识

        返回：
            模型元数据对象，不存在时返回 None
        """
        stmt = select(Metadata).where(Metadata.model_id == model_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_models(self) -> list[Metadata]:
        """获取所有活跃模型

        返回：
            活跃模型列表
        """
        stmt = select(Metadata).where(Metadata.status == "active")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_models(self, **filters) -> list[Metadata]:
        """获取模型列表

        参数：
            **filters: 模型字段过滤条件，支持 status、model_type、framework 等字段

        返回：
            模型列表，按创建时间倒序排列
        """
        stmt = select(Metadata)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(Metadata.created_at.desc())

        result = await self.session.execute(stmt)

        return list(result.scalars().all())