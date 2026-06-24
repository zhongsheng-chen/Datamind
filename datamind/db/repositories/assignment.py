# datamind/db/repositories/assignment.py

"""实验分配仓储

用于查询与写入实验主体的固定分配关系，
保证同一个主体在同一个实验中稳定命中同一个分组。

核心功能：
  - get_assignment: 获取实验分配记录
  - get_subject_assignment: 获取主体在实验中的固定分配
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
      repo = AssignmentRepository(uow.session)

      assignment = repo.create_assignment(
          assignment_id="asn_a1b2c3d4",
          experiment_id="exp_a1b2c3d4",
          variant_id="var_a1b2c3d4",
          subject_key="customer_10001",
          subject_type="customer",
          strategy=AssignmentStrategy.HASH,
          bucket="bucket_0123",
          weight=0.5,
          context={"group": "treatment"}
      )
"""

from datetime import datetime, timezone
from sqlalchemy import select

from datamind.db.models.assignments import Assignment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import AssignmentStrategy


class AssignmentRepository(BaseRepository):
    """实验分配仓储"""

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
        stmt = select(Assignment).where(
            Assignment.assignment_id == assignment_id
        )
        result = await self.session.execute(stmt)

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
        stmt = select(Assignment).where(
            Assignment.experiment_id == experiment_id,
            Assignment.subject_key == subject_key,
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def list_assignments(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        **filters,
    ) -> list[Assignment]:
        """获取实验分配记录列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            **filters: 过滤条件
                支持字段：
                    experiment_id
                    variant_id
                    subject_key
                    subject_type
                    strategy
                    bucket

        返回：
            实验分配记录列表，按分配时间倒序排列
        """
        stmt = select(Assignment)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(
            Assignment.assigned_at.desc(),
            Assignment.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

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
            实验分配记录列表，按分配时间倒序排列
        """
        filters = {
            "experiment_id": experiment_id,
        }

        return await self.list_assignments(
            limit=limit,
            offset=offset,
            **filters,
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
            实验分配记录列表，按分配时间倒序排列
        """
        filters = {
            "variant_id": variant_id,
        }

        return await self.list_assignments(
            limit=limit,
            offset=offset,
            **filters,
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
            实验分配记录列表，按分配时间倒序排列
        """
        filters = {
            "subject_key": subject_key,
        }

        return await self.list_assignments(
            limit=limit,
            offset=offset,
            **filters,
        )

    def create_assignment(
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
        """
        obj = Assignment(
            assignment_id=assignment_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            subject_key=subject_key,
            subject_type=subject_type,
            strategy=strategy,
            bucket=bucket,
            weight=weight,
            context=context,
            assigned_at=assigned_at or datetime.now(timezone.utc),
        )

        self.add(obj)

        return obj