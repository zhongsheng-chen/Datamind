"""实验分组仓储

提供实验分组的查询、创建、更新和生命周期管理能力。

核心功能：
  - get_variant: 获取实验分组
  - get_control_variant: 获取实验对照组
  - list_variants: 获取实验分组列表
  - list_active_variants: 获取启用的实验分组
  - create_variant: 创建实验分组
  - update_variant: 更新实验分组
  - activate_variant: 启用实验分组
  - deactivate_variant: 停用实验分组
  - archive_variant: 归档实验分组
  - mark_deleted: 逻辑删除实验分组
  - restore_variant: 恢复实验分组

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.variant import (
      VariantPatch,
      VariantRepository,
  )

  async with UnitOfWork() as uow:
      repo = VariantRepository(
          uow.session
      )

      variant = repo.create_variant(
          variant_id="var_0123456789abcdef",
          experiment_id="exp_0123456789abcdef",
          name="treatment",
          deployment_id="dep_0123456789abcdef",
          weight=0.5,
          is_control=False,
          created_by="system",
      )
"""

from dataclasses import (
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.db.models.variants import Variant
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import ExperimentVariantStatus


@dataclass(slots=True)
class VariantPatch:
    """实验分组更新结构

    注意：
        不允许通过 patch 修改 status，
        实验分组状态由生命周期方法控制。

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

    @staticmethod
    def _validate_weight(
            weight: float,
    ) -> None:
        """校验实验分组权重"""
        if (
                weight < 0
                or weight > 1
        ):
            raise ValueError(
                "实验分组 weight 必须在 0 到 1 之间"
            )

    @staticmethod
    def _set_variant_status(
            variant: Variant,
            *,
            target_status: ExperimentVariantStatus,
            updated_by: str | None,
    ) -> Variant:
        """设置实验分组状态"""
        current_status = ExperimentVariantStatus(
            variant.status
        )

        if current_status == target_status:
            return variant

        if (
                current_status
                == ExperimentVariantStatus.ARCHIVED
        ):
            raise ValueError(
                "archived 实验分组不能修改状态"
            )

        variant.status = str(
            target_status
        )

        if updated_by is not None:
            variant.updated_by = updated_by

        return variant

    async def get_variant(
            self,
            variant_id: str,
            *,
            include_deleted: bool = False,
    ) -> Variant | None:
        """获取实验分组

        参数：
            variant_id: 实验分组 ID
            include_deleted: 是否包含逻辑删除记录

        返回：
            实验分组对象，不存在时返回 None
        """
        stmt = select(
            Variant
        ).where(
            Variant.variant_id
            == variant_id
        )

        if not include_deleted:
            stmt = stmt.where(
                Variant.deleted_at.is_(
                    None
                )
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_control_variant(
            self,
            experiment_id: str,
    ) -> Variant | None:
        """获取实验对照组

        参数：
            experiment_id: 实验 ID

        返回：
            启用的对照组对象，不存在时返回 None
        """
        stmt = (
            select(
                Variant
            )
            .where(
                Variant.experiment_id
                == experiment_id,
                Variant.is_control.is_(
                    True
                ),
                Variant.status
                == str(
                    ExperimentVariantStatus.ACTIVE
                ),
                Variant.deleted_at.is_(
                    None
                ),
            )
            .order_by(
                Variant.created_at.asc()
            )
            .limit(
                1
            )
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_variants(
            self,
            *,
            variant_id: str | None = None,
            experiment_id: str | None = None,
            name: str | None = None,
            deployment_id: str | None = None,
            status: ExperimentVariantStatus | None = None,
            is_control: bool | None = None,
            created_by: str | None = None,
            include_deleted: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Variant]:
        """获取实验分组列表

        参数：
            variant_id: 实验分组 ID（可选）
            experiment_id: 实验 ID（可选）
            name: 实验分组名称（可选）
            deployment_id: 部署 ID（可选）
            status: 实验分组状态（可选）
            is_control: 是否为对照组（可选）
            created_by: 创建人（可选）
            include_deleted: 是否包含逻辑删除记录
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验分组列表，按更新时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        if (
                limit is not None
                and limit < 0
        ):
            raise ValueError(
                "limit 不能小于 0"
            )

        if (
                offset is not None
                and offset < 0
        ):
            raise ValueError(
                "offset 不能小于 0"
            )

        stmt = select(
            Variant
        )

        if not include_deleted:
            stmt = stmt.where(
                Variant.deleted_at.is_(
                    None
                )
            )

        if variant_id is not None:
            stmt = stmt.where(
                Variant.variant_id
                == variant_id
            )

        if experiment_id is not None:
            stmt = stmt.where(
                Variant.experiment_id
                == experiment_id
            )

        if name is not None:
            stmt = stmt.where(
                Variant.name
                == name
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Variant.deployment_id
                == deployment_id
            )

        if status is not None:
            stmt = stmt.where(
                Variant.status
                == str(
                    status
                )
            )

        if is_control is not None:
            stmt = stmt.where(
                Variant.is_control
                == is_control
            )

        if created_by is not None:
            stmt = stmt.where(
                Variant.created_by
                == created_by
            )

        stmt = stmt.order_by(
            Variant.updated_at.desc(),
            Variant.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

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
            启用的实验分组列表
        """
        return await self.list_variants(
            experiment_id=experiment_id,
            status=ExperimentVariantStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_variant(
            self,
            *,
            variant_id: str,
            experiment_id: str,
            name: str,
            deployment_id: str,
            weight: float,
            is_control: bool = False,
            status: ExperimentVariantStatus = (
                ExperimentVariantStatus.ACTIVE
            ),
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
        self._validate_weight(
            weight
        )

        new_variant = Variant(
            variant_id=variant_id,
            experiment_id=experiment_id,
            name=name,
            deployment_id=deployment_id,
            weight=float(
                weight
            ),
            is_control=is_control,
            status=str(
                status
            ),
            config=config,
        )

        if description is not None:
            new_variant.description = description

        if created_by is not None:
            new_variant.created_by = created_by

        self.add(
            new_variant
        )

        return new_variant

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
            self._validate_weight(
                patch.weight
            )

        for field in fields(
                VariantPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            setattr(
                variant,
                field.name,
                value,
            )

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

        archived 为终态，归档后不能重新启用。
        """
        return self._set_variant_status(
            variant,
            target_status=(
                ExperimentVariantStatus.ACTIVE
            ),
            updated_by=updated_by,
        )

    def deactivate_variant(
            self,
            variant: Variant,
            *,
            updated_by: str | None = None,
    ) -> Variant:
        """停用实验分组

        archived 为终态，归档后不能重新停用。
        """
        return self._set_variant_status(
            variant,
            target_status=(
                ExperimentVariantStatus.INACTIVE
            ),
            updated_by=updated_by,
        )

    def archive_variant(
            self,
            variant: Variant,
            *,
            updated_by: str | None = None,
    ) -> Variant:
        """归档实验分组

        active 和 inactive 状态均可归档；
        archived 状态重复归档保持幂等。
        """
        return self._set_variant_status(
            variant,
            target_status=(
                ExperimentVariantStatus.ARCHIVED
            ),
            updated_by=updated_by,
        )

    @staticmethod
    def mark_deleted(
            variant: Variant,
            *,
            deletion_id: str,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_reason: str | None = None,
    ) -> Variant:
        """逻辑删除实验分组"""
        variant.deleted_at = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        variant.deleted_by = deleted_by
        variant.deletion_id = deletion_id
        variant.deletion_reason = deletion_reason
        variant.updated_by = deleted_by

        return variant

    @staticmethod
    def restore_variant(
            variant: Variant,
            *,
            restored_by: str | None = None,
    ) -> Variant:
        """恢复逻辑删除的实验分组"""
        variant.deleted_at = None
        variant.deleted_by = None
        variant.deletion_id = None
        variant.deletion_reason = None
        variant.updated_by = restored_by

        return variant
