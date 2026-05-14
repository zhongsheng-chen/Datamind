# datamind/db/repositories/metadata.py

"""模型元数据访问器

提供模型元数据的查询与更新能力。

核心功能：
  - get_model: 获取单个模型（支持 model_id 或 name）
  - list_active_models: 获取活跃模型列表
  - list_models: 获取模型列表（支持过滤、分页）
  - create_model: 创建模型
  - update_model: 更新模型元数据
  - archive_model: 归档模型
  - activate_model: 激活模型
  - deprecate_model: 标记模型废弃

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import MetadataRepository, MetadataPatch

  async with UnitOfWork() as uow:
      repo = MetadataRepository(uow.session)

      model = await repo.create_model(
          model_id="mdl_a1b2c3d4",
          name="scorecard",
          model_type="logistic_regression",
          task_type="scoring",
          framework="sklearn",
          description="基于逻辑回归的信用评分模型"
      )

"""

from datetime import datetime, timezone
from dataclasses import dataclass, fields
from sqlalchemy import select

from datamind.db.models.metadata import Metadata
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import MetadataStatus


@dataclass(slots=True)
class MetadataPatch:
    """模型元数据更新结构

    注意：
        不允许通过 patch 修改 status（由生命周期方法控制）

    属性：
        name: 模型名称
        model_type: 模型类型
        task_type: 任务类型
        framework: 框架类型
        description: 模型描述
        input_schema: 输入 Schema
        output_schema: 输出 Schema
        updated_by: 更新人
    """
    name: str | None = None
    model_type: str | None = None
    task_type: str | None = None
    framework: str | None = None
    description: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    updated_by: str | None = None


class MetadataRepository(BaseRepository):
    """模型元数据访问器"""

    async def get_model(
        self,
        *,
        model_id: str | None = None,
        name: str | None = None,
    ) -> Metadata | None:
        """获取单个模型

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）

        返回：
            模型对象，不存在时返回 None

        异常：
            ValueError: model_id 和 name 同时提供或同时未提供
        """
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
        """获取活跃模型列表

        返回：
            活跃模型列表，按更新时间倒序排列
        """
        stmt = (
            select(Metadata)
            .where(Metadata.status == MetadataStatus.ACTIVE)
            .order_by(Metadata.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_models(
        self,
        *,
        exclude_status: MetadataStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **filters,
    ) -> list[Metadata]:
        """获取模型列表

        参数：
            exclude_status: 排除指定状态
            limit: 返回数量限制
            offset: 分页偏移
            **filters: 过滤条件，支持 status、framework、model_type、task_type、created_by

        返回：
            模型列表，按更新时间倒序排列
        """
        stmt = select(Metadata)

        if filters:
            stmt = stmt.filter_by(**filters)

        if exclude_status:
            stmt = stmt.where(Metadata.status != exclude_status)

        stmt = stmt.order_by(
            Metadata.updated_at.desc(),
            Metadata.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_model(
        self,
        *,
        model_id: str,
        name: str,
        model_type: str,
        task_type: str,
        framework: str,
        description: str | None = None,
        input_schema: dict | None = None,
        output_schema: dict | None = None,
        status: MetadataStatus = MetadataStatus.ACTIVE,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> Metadata:
        """创建模型

        参数：
            model_id: 模型 ID
            name: 模型名称
            model_type: 模型类型
            task_type: 任务类型
            framework: 框架类型
            description: 模型描述（可选）
            input_schema: 输入 Schema（可选）
            output_schema: 输出 Schema（可选）
            status: 模型状态（默认 ACTIVE）
            created_by: 创建人（可选）
            updated_by: 更新人（可选）

        返回：
            创建后的模型对象
        """
        obj = Metadata(
            model_id=model_id,
            name=name,
            model_type=model_type,
            task_type=task_type,
            framework=framework,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            status=status,
            created_by=created_by,
            updated_by=updated_by,
        )

        self.add(obj)
        return obj

    def update_model(
        self, metadata: Metadata,
        patch: MetadataPatch,
        *,
        updated_by: str | None = None
    ) -> Metadata:
        """更新模型元数据

        参数：
            model: 模型对象
            patch: 更新内容

        返回：
            更新后的模型对象
        """
        for field in fields(MetadataPatch):
            field_name = field.name

            if field_name == "status":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(metadata, field_name, value)

        if updated_by is not None:
            metadata.updated_by = updated_by

        metadata.updated_at = datetime.now(timezone.utc)

        return metadata

    def archive_model(
        self,
        metadata: Metadata,
        *,
        updated_by: str | None = None
    ) -> Metadata:
        """归档模型

        参数：
            model: 模型对象
            updated_by: 更新人（可选）

        返回：
            归档后的模型对象
        """
        metadata.status = MetadataStatus.ARCHIVED

        if updated_by:
            metadata.updated_by = updated_by

        return metadata

    def activate_model(
        self,
        metadata: Metadata,
        *,
        updated_by: str | None = None
    ) -> Metadata:
        """激活模型

        参数：
            metadata: 模型对象
            updated_by: 更新人（可选）

        返回：
            激活后的模型对象
        """
        metadata.status = MetadataStatus.ACTIVE

        if updated_by:
            metadata.updated_by = updated_by

        return metadata

    def deprecate_model(
        self,
        metadata: Metadata,
        *,
        updated_by: str | None = None
    ) -> Metadata:
        """标记模型废弃

        参数：
            metadata: 模型对象
            updated_by: 更新人（可选）

        返回：
            废弃后的模型对象
        """
        metadata.status = MetadataStatus.DEPRECATED

        if updated_by:
            metadata.updated_by = updated_by

        return metadata