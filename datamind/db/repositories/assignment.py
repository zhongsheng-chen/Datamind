# datamind/db/repositories/assignment.py

"""实验分配仓储

用于查询与写入实验主体的固定分配关系，
保证同一个主体在同一个实验中稳定命中同一个分组。

核心功能：
  - get_assignment: 获取实验分配记录
  - get_subject_assignment: 获取主体在实验中的固定分配
  - get_or_create_assignment: 原子获取或创建主体固定分配
  - list_assignments: 获取实验分配记录列表
  - list_experiment_assignments: 获取实验分配记录
  - list_variant_assignments: 获取实验分组分配记录
  - list_subject_assignments: 获取主体参与的实验分配记录
  - create_assignment: 创建实验分配记录

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.assignment import AssignmentRepository
  from datamind.models.enums import AssignmentStrategy

  async with UnitOfWork() as uow:
      repo = AssignmentRepository(
          uow.session
      )

      assignment = repo.create_assignment(
          assignment_id="asn_0123456789abcdef",
          experiment_id="exp_0123456789abcdef",
          variant_id="var_0123456789abcdef",
          subject_key="customer_10001",
          subject_type="customer",
          strategy=AssignmentStrategy.HASH,
          bucket="bucket_0123",
          weight=0.5,
          context={
              "group": "treatment",
          },
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from datamind.db.models.assignments import Assignment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import AssignmentStrategy


class AssignmentRepository(BaseRepository):
    """实验分配仓储"""

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数"""
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

    @staticmethod
    def _validate_weight(
            weight: float | None,
    ) -> None:
        """校验实验分组权重"""
        if weight is None:
            return

        if (
                weight < 0
                or weight > 1
        ):
            raise ValueError(
                "实验分配 weight 必须在 0 到 1 之间"
            )

    async def get_assignment(
            self,
            assignment_id: str,
    ) -> Assignment | None:
        """获取实验分配记录

        参数：
            assignment_id: 分配 ID

        返回：
            实验分配记录对象，不存在时返回 None
        """
        stmt = select(
            Assignment
        ).where(
            Assignment.assignment_id
            == assignment_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_subject_assignment(
            self,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> Assignment | None:
        """获取主体在实验中的固定分配

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体标识，例如客户号、订单号、申请单号

        返回：
            实验分配记录对象，不存在时返回 None
        """
        stmt = select(
            Assignment
        ).where(
            Assignment.experiment_id
            == experiment_id,
            Assignment.subject_key
            == subject_key,
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_or_create_assignment(
            self,
            *,
            assignment_id: str,
            experiment_id: str,
            variant_id: str,
            subject_key: str,
            subject_type: str | None = None,
            strategy: AssignmentStrategy = AssignmentStrategy.HASH,
            bucket: str | None = None,
            weight: float | None = None,
            context: dict | None = None,
            assigned_at: datetime | None = None,
    ) -> tuple[Assignment, bool]:
        """原子获取或创建主体的固定实验分配"""
        self._validate_weight(weight)

        stmt = insert(Assignment).values(
            assignment_id=assignment_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            subject_key=subject_key,
            subject_type=subject_type,
            strategy=str(strategy),
            bucket=bucket,
            weight=weight,
            context=context,
            assigned_at=(
                assigned_at
                if assigned_at is not None
                else datetime.now(timezone.utc)
            ),
        ).on_conflict_do_nothing(
            index_elements=[
                Assignment.experiment_id,
                Assignment.subject_key,
            ]
        ).returning(Assignment)

        result = await self.session.execute(stmt)
        assignment: Assignment | None = (
            result.scalar_one_or_none()
        )

        if assignment is not None:
            return assignment, True

        existing = await self.get_subject_assignment(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        if existing is None:
            raise RuntimeError("固定实验分配写入失败")

        return existing, False

    async def list_assignments(
            self,
            *,
            assignment_id: str | None = None,
            experiment_id: str | None = None,
            variant_id: str | None = None,
            subject_key: str | None = None,
            subject_type: str | None = None,
            strategy: AssignmentStrategy | None = None,
            bucket: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Assignment]:
        """获取实验分配记录列表

        参数：
            assignment_id: 分配 ID（可选）
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            subject_key: 分桶主体标识（可选）
            subject_type: 分桶主体类型（可选）
            strategy: 分配策略（可选）
            bucket: 分桶标识（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验分配记录列表，按分配时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Assignment
        )

        if assignment_id is not None:
            stmt = stmt.where(
                Assignment.assignment_id
                == assignment_id
            )

        if experiment_id is not None:
            stmt = stmt.where(
                Assignment.experiment_id
                == experiment_id
            )

        if variant_id is not None:
            stmt = stmt.where(
                Assignment.variant_id
                == variant_id
            )

        if subject_key is not None:
            stmt = stmt.where(
                Assignment.subject_key
                == subject_key
            )

        if subject_type is not None:
            stmt = stmt.where(
                Assignment.subject_type
                == subject_type
            )

        if strategy is not None:
            stmt = stmt.where(
                Assignment.strategy
                == str(
                    strategy
                )
            )

        if bucket is not None:
            stmt = stmt.where(
                Assignment.bucket
                == bucket
            )

        stmt = stmt.order_by(
            Assignment.assigned_at.desc(),
            Assignment.created_at.desc(),
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

    async def list_experiment_assignments(
            self,
            experiment_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Assignment]:
        """获取实验分配记录

        参数：
            experiment_id: 实验 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验分配记录列表，按分配时间和创建时间倒序排列
        """
        return await self.list_assignments(
            experiment_id=experiment_id,
            limit=limit,
            offset=offset,
        )

    async def list_variant_assignments(
            self,
            variant_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Assignment]:
        """获取实验分组分配记录

        参数：
            variant_id: 实验分组 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验分配记录列表，按分配时间和创建时间倒序排列
        """
        return await self.list_assignments(
            variant_id=variant_id,
            limit=limit,
            offset=offset,
        )

    async def list_subject_assignments(
            self,
            subject_key: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Assignment]:
        """获取主体参与的实验分配记录

        参数：
            subject_key: 分桶主体标识
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验分配记录列表，按分配时间和创建时间倒序排列
        """
        return await self.list_assignments(
            subject_key=subject_key,
            limit=limit,
            offset=offset,
        )

    def create_assignment(
            self,
            *,
            assignment_id: str,
            experiment_id: str,
            variant_id: str,
            subject_key: str,
            subject_type: str | None = None,
            strategy: AssignmentStrategy = (
                AssignmentStrategy.HASH
            ),
            bucket: str | None = None,
            weight: float | None = None,
            context: dict | None = None,
            assigned_at: datetime | None = None,
    ) -> Assignment:
        """创建实验分配记录

        参数：
            assignment_id: 分配 ID
            experiment_id: 实验 ID
            variant_id: 实验分组 ID
            subject_key: 分桶主体标识
            subject_type: 分桶主体类型（可选）
            strategy: 分配策略
            bucket: 分桶标识（可选）
            weight: 命中分组的权重（可选）
            context: 分配上下文（可选）
            assigned_at: 分配时间（可选）

        返回：
            创建后的实验分配记录对象

        异常：
            ValueError: weight 不在 0 到 1 之间
        """
        self._validate_weight(
            weight
        )

        new_assignment = Assignment(
            assignment_id=assignment_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            subject_key=subject_key,
            strategy=str(
                strategy
            ),
            assigned_at=(
                assigned_at
                if assigned_at is not None
                else datetime.now(
                    timezone.utc
                )
            ),
        )

        if subject_type is not None:
            new_assignment.subject_type = subject_type

        if bucket is not None:
            new_assignment.bucket = bucket

        if weight is not None:
            new_assignment.weight = weight

        if context is not None:
            new_assignment.context = context

        self.add(
            new_assignment
        )

        return new_assignment
