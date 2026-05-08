# datamind/db/reader/assignment_reader.py

"""分配记录读取器

用于查询请求分配结果，支持 AB 测试与流量分析。

使用示例：
    reader = AssignmentReader(session)

    assignment = await reader.get_assignment("req_a1b2c3d4")
    assignments = await reader.list_model_assignments("mdl_a1b2c3d4", limit=20)
"""

from sqlalchemy import select

from datamind.db.models.assignments import Assignment
from datamind.db.readers.base_reader import BaseReader


class AssignmentReader(BaseReader):
    """分配记录读取器"""

    async def get_assignment(self, request_id: str) -> Assignment | None:
        """获取请求的分配结果

        参数：
            request_id: 请求唯一标识

        返回：
            分配记录对象，不存在时返回 None
        """
        stmt = select(Assignment).where(Assignment.request_id == request_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_model_assignments(
        self,
        model_id: str,
        limit: int = 100,
    ) -> list[Assignment]:
        """获取模型的分配记录

        参数：
            model_id: 模型 ID
            limit: 返回记录数量上限，默认为 100

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

    async def list_experiment_assignments(
        self,
        experiment_id: str,
        limit: int = 100,
    ) -> list[Assignment]:
        """获取实验相关的分配记录

        参数：
            experiment_id: 实验唯一标识
            limit: 返回记录数量上限，默认为 100

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