# datamind/db/reader/audit_reader.py

"""审计日志读取器

用于查询系统操作记录，支持变更追踪与问题回溯。

使用示例：
    reader = AuditReader(session)

    history = await reader.list_entity_history("model", "mdl_a1b2c3d4")
    failures = await reader.list_failed_operations(limit=50)
"""

from sqlalchemy import select

from datamind.db.models.audit import Audit
from datamind.db.readers.base_reader import BaseReader


class AuditReader(BaseReader):
    """审计日志读取器"""

    async def list_entity_history(
        self,
        target_type: str,
        target_id: str,
    ) -> list[Audit]:
        """获取某个实体的变更历史

        参数：
            target_type: 目标类型（model / version / deployment / experiment）
            target_id: 目标 ID

        返回：
            审计日志列表，按发生时间正序排列
        """
        stmt = (
            select(Audit)
            .where(
                Audit.target_type == target_type,
                Audit.target_id == target_id,
            )
            .order_by(Audit.occurred_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_failed_operations(
        self,
        limit: int = 100,
    ) -> list[Audit]:
        """获取失败操作记录

        参数：
            limit: 返回记录数量上限，默认为 100

        返回：
            失败操作列表，按发生时间倒序排列
        """
        stmt = (
            select(Audit)
            .where(Audit.status == "failed")
            .order_by(Audit.occurred_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_user_actions(
        self,
        user: str,
        limit: int = 100,
    ) -> list[Audit]:
        """获取用户操作记录

        参数：
            user: 操作者用户名
            limit: 返回记录数量上限，默认为 100

        返回：
            用户操作列表，按发生时间倒序排列
        """
        stmt = (
            select(Audit)
            .where(Audit.user == user)
            .order_by(Audit.occurred_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())