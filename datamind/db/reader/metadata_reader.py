# datamind/db/reader/metadata_reader.py

"""模型元数据读取器

提供模型元数据的查询能力。

使用示例：
    reader = MetadataReader(session)

    model = await reader.get_model("mdl_a1b2c3d4")
    models = await reader.list_active_models()
"""

from sqlalchemy import select

from datamind.db.models.metadata import Metadata
from datamind.db.reader.base_reader import BaseReader


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