# datamind/db/repositories/variant.py

"""实验分组仓储

提供实验分组的查询与管理能力。

核心功能：
  - get_variant: 获取实验分组
  - list_variants: 获取实验分组列表
  - list_active_variants: 获取启用的实验分组
  - create_variant: 创建实验分组
  - update_variant: 更新实验分组
  - activate_variant: 启用实验分组
  - deactivate_variant: 停用实验分组
  - archive_variant: 归档实验分组

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.variant import VariantRepository

  async with UnitOfWork() as uow:
      repo = VariantRepository(uow.session)

      variant = repo.create_variant(
          variant_id="var_a1b2c3d4",
          experiment_id="exp_a1b2c3d4",
          name="treatment",
          deployment_id="dep_a1b2c3d4",
          weight=0.5,
          is_control=False,
          created_by="system"
      )
"""

from dataclasses import dataclass, fields

from sqlalchemy import select

from datamind.db.models.variants import Variant
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import ExperimentVariantStatus


@dataclass(slots=True)
class VariantPatch:
    """实验分组更新结构

    注意：
        不允许通过 patch 修改 status，由生命周期方法控制

    属性：
        name: 实验分组名称
        deployment_id: 部署 ID
        weight: 实验内分组权重
        is_control: 是否为对照组
        config: 实验分组配置
        description: 实验分组说明
    """

    name: str | None = None
    deployment_id: str | None = None
    weight: float | None = None
    is_control: bool | None = None
    config: dict | None = None
    description: str | None = None


class VariantRepository(BaseRepository):
    """实验分组仓储"""

    async def get_variant(
        self,
        variant_id: str,
    ) -> Variant | None:
        """获取实验分组

        参数：
            variant_id: 实验分组 ID

        返回：
            实验分组对象，不存在时返回 None
        """
        stmt = select(Variant).where(Variant.variant_id == variant_id)
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def list_variants(
            self,
            *,
            limit: int | None = None,
            offset: int | None = None,
            **filters,
    ) -> list[Variant]:
        """获取实验分组列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            **filters: 过滤条件
                支持字段：
                    experiment_id
                    deployment_id
                    status
                    is_control
                    created_by

        返回：
            实验分组列表，按更新时间倒序排列
        """
        stmt = select(Variant)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(
            Variant.updated_at.desc(),
            Variant.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_active_variants(
            self,
            experiment_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Variant]:
        """获取启用的实验分组

        参数：
            experiment_id: 实验 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            启用的实验分组列表，按更新时间倒序排列
        """
        filters = {
            "experiment_id": experiment_id,
            "status": ExperimentVariantStatus.ACTIVE,
        }

        return await self.list_variants(
            limit=limit,
            offset=offset,
            **filters,
        )

    async def get_control_variant(
        self,
        experiment_id: str,
    ) -> Variant | None:
        """获取实验对照组

        参数：
            experiment_id: 实验 ID

        返回：
            对照组对象，不存在时返回 None
        """
        stmt = (
            select(Variant)
            .where(
                Variant.experiment_id == experiment_id,
                Variant.is_control == True,
                Variant.status == ExperimentVariantStatus.ACTIVE,
            )
            .order_by(Variant.created_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    def create_variant(
        self,
        *,
        variant_id: str,
        experiment_id: str,
        name: str,
        deployment_id: str,
        weight: float,
        is_control: bool = False,
        status: ExperimentVariantStatus = ExperimentVariantStatus.ACTIVE,
        config: dict | None = None,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Variant:
        """创建实验分组

        参数：
            variant_id: 实验分组 ID
            experiment_id: 实验 ID
            name: 实验分组名称
            deployment_id: 部署 ID
            weight: 实验内分组权重
            is_control: 是否为对照组
            status: 实验分组状态
            config: 实验分组配置（可选）
            description: 实验分组说明（可选）
            created_by: 创建人（可选）

        返回：
            创建后的实验分组对象

        异常：
            ValueError: weight 不在 0 到 1 之间
        """
        if weight < 0 or weight > 1:
            raise ValueError("实验分组 weight 必须在 0 到 1 之间")

        obj = Variant(
            variant_id=variant_id,
            experiment_id=experiment_id,
            name=name,
            deployment_id=deployment_id,
            weight=weight,
            is_control=is_control,
            status=status,
            config=config,
            description=description,
            created_by=created_by,
        )

        self.add(obj)

        return obj

    def update_variant(
        self,
        variant: Variant,
        patch: VariantPatch,
        *,
        updated_by: str | None = None,
    ) -> Variant:
        """更新实验分组

        参数：
            variant: 实验分组对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的实验分组对象

        异常：
            ValueError: weight 不在 0 到 1 之间
        """
        if patch.weight is not None:
            if patch.weight < 0 or patch.weight > 1:
                raise ValueError("实验分组 weight 必须在 0 到 1 之间")

        for field in fields(VariantPatch):
            value = getattr(patch, field.name)

            if value is None:
                continue

            setattr(variant, field.name, value)

        if updated_by is not None:
            variant.updated_by = updated_by

        return variant

    def activate_variant(
        self,
        variant: Variant,
        *,
        updated_by: str | None = None,
    ) -> Variant:
        """启用实验分组

        参数：
            variant: 实验分组对象
            updated_by: 更新人（可选）

        返回：
            启用后的实验分组对象
        """
        variant.status = ExperimentVariantStatus.ACTIVE

        if updated_by:
            variant.updated_by = updated_by

        return variant

    def deactivate_variant(
        self,
        variant: Variant,
        *,
        updated_by: str | None = None,
    ) -> Variant:
        """停用实验分组

        参数：
            variant: 实验分组对象
            updated_by: 更新人（可选）

        返回：
            停用后的实验分组对象
        """
        variant.status = ExperimentVariantStatus.INACTIVE

        if updated_by:
            variant.updated_by = updated_by

        return variant

    def archive_variant(
        self,
        variant: Variant,
        *,
        updated_by: str | None = None,
    ) -> Variant:
        """归档实验分组

        参数：
            variant: 实验分组对象
            updated_by: 更新人（可选）

        返回：
            归档后的实验分组对象
        """
        variant.status = ExperimentVariantStatus.ARCHIVED

        if updated_by:
            variant.updated_by = updated_by

        return variant