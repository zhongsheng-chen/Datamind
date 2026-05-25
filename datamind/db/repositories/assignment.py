# datamind/db/repositories/assignment.py

"""分配记录访问器

用于查询与写入请求分配结果，支持 AB 测试与灰度发布审计。

核心功能：
  - get_assignment: 获取请求的分配结果
  - list_model_assignments: 获取模型分配记录
  - list_experiment_assignments: 获取实验分配记录
  - create_assignment: 创建分配记录

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.assignment import AssignmentRepository

  async with UnitOfWork() as uow:
      repo = AssignmentRepository(uow.session)

      assignment = await repo.create_assignment(
          assignment_id="asn_a1b2c3d4",
          request_id="req_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          version_id="ver_a1b2c3d4",
          deployment_id="dep_a1b2c3d4",
          experiment_id="exp_a1b2c3d4",
          customer_id="cus_a1b2c3d4",
          source="experiment",
          strategy="consistent",
          bucket="89",
          group="treatment",
          weight=0.1,
          context={"experiment_id": "exp_a1b2c3d4", "group": "treatment"}
      )
"""

from datetime import datetime, timezone

from sqlalchemy import select

from datamind.db.models.assignments import Assignment
from datamind.db.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository):
    """分配记录访问器"""

    async def get_assignment(self, request_id: str) -> Assignment | None:
        """获取请求的分配结果

        参数：
            request_id: 请求 ID

        返回：
            分配记录对象，不存在时返回 None
        """
        stmt = select(Assignment).where(Assignment.request_id == request_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_model_assignments(self, model_id: str, limit: int = 100) -> list[Assignment]:
        """获取模型分配记录

        参数：
            model_id: 模型 ID
            limit: 返回数量限制

        返回：
            分配记录列表，按创建时间倒序排列
        """
        stmt = (
            select(Assignment)
            .where(Assignment.model_id == model_id)
            .order_by(Assignment.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_experiment_assignments(self, experiment_id: str, limit: int = 100) -> list[Assignment]:
        """获取实验分配记录

        参数：
            experiment_id: 实验 ID
            limit: 返回数量限制

        返回：
            分配记录列表，按创建时间倒序排列
        """
        stmt = (
            select(Assignment)
            .where(Assignment.context.contains({"experiment_id": experiment_id}))
            .order_by(Assignment.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_assignment(
        self,
        *,
        assignment_id: str,
        request_id: str,
        model_id: str,
        version_id: str,
        deployment_id: str,
        experiment_id: str,
        customer_id: str,
        source: str,
        strategy: str | None = None,
        bucket: str | None = None,
        group: str | None = None,
        weight: float | None = None,
        context: dict | None = None,
        routed_at: datetime | None = None,
    ) -> Assignment:
        """创建分配记录

        参数：
            assignment_id: 分配记录 ID
            request_id: 请求 ID
            model_id: 模型 ID
            version_id: 版本 ID
            deployment_id: 部署 ID
            experiment_id: 实验 ID
            customer_id: 客户 ID
            source: 分配来源
            strategy: 分配策略（可选）
            bucket: 桶编号（可选）
            group: 实验组别（可选）
            weight: 流量权重（可选）
            context: 分配上下文（可选）
            routed_at: 路由时间（可选）

        返回：
            创建后的分配记录对象
        """
        obj = Assignment(
            assignment_id=assignment_id,
            request_id=request_id,
            model_id=model_id,
            version_id=version_id,
            deployment_id=deployment_id,
            experiment_id=experiment_id,
            customer_id=customer_id,
            source=source,
            strategy=strategy,
            bucket=bucket,
            group=group,
            weight=weight,
            context=context,
            routed_at=routed_at or datetime.now(timezone.utc),
        )

        self.add(obj)
        return obj