# datamind/db/reader/metadata_reader.py

"""模型元数据读取器

提供模型元数据的查询能力。

核心功能：
  - get_model: 获取模型信息（支持 model_id 或 name，二选一）
  - list_active_models: 获取所有活跃模型
  - list_models: 获取模型列表（支持过滤、分页）

使用示例：
  from datamind.db.reader.metadata_reader import MetadataReader

  reader = MetadataReader(session)

  # 获取单个模型，按 ID 查询
  model = await reader.get_model(model_id="mdl_a1b2c3d4")

  # 获取单个模型，按名称查询
  model = await reader.get_model(name="scorecard")

  # 获取所有活跃模型
  active_models = await reader.list_active_models()

  # 条件过滤
  models = await reader.list_models(
      status="active",
      framework="sklearn",
      limit=10,
      offset=0,
  )

  # 排除已归档模型
  models = await reader.list_models(
      exclude_status="archived",
      model_type="logistic_regression",
  )
"""

from sqlalchemy import select

from datamind.db.models.metadata import Metadata
from datamind.db.readers.base_reader import BaseReader


class MetadataReader(BaseReader):
    """模型元数据读取器"""

    async def get_model(
        self,
        *,
        model_id: str | None = None,
        name: str | None = None,
    ) -> Metadata | None:
        """获取单个模型

        参数：
            model_id: 模型ID（可选）
            name: 模型名称（可选）

        返回：
            模型元数据对象，不存在时返回 None

        异常：
            ValueError: model_id 和 name 同时提供或同时未提供
        """
        # 必须且只能提供一个
        if bool(model_id) == bool(name):
            raise ValueError("必须且只能提供 model_id 或 name 其中一个")

        stmt = select(Metadata)

        if model_id:
            stmt = stmt.where(Metadata.model_id == model_id)
        else:
            stmt = stmt.where(Metadata.name == name)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_models(self) -> list[Metadata]:
        """获取所有活跃模型

        返回：
            活跃模型列表，按更新时间倒序排列
        """
        stmt = (
            select(Metadata)
            .where(Metadata.status == "active")
            .order_by(Metadata.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_models(
        self,
        *,
        exclude_status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **filters,
    ) -> list[Metadata]:
        """获取模型列表

        参数：
            exclude_status: 排除指定状态，如 archived
            limit: 返回数量限制
            offset: 分页偏移
            **filters: 过滤条件，支持 status、framework、model_type、task_type、created_by

        返回：
            模型列表，按更新时间倒序排列
        """
        stmt = select(Metadata)

        # 精确字段过滤
        if filters:
            stmt = stmt.filter_by(**filters)

        # 排除状态
        if exclude_status:
            stmt = stmt.where(Metadata.status != exclude_status)

        # 排序
        stmt = stmt.order_by(
            Metadata.updated_at.desc(),
            Metadata.created_at.desc(),
        )

        # 分页
        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())