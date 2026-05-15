# datamind/db/repositories/audit.py

"""审计日志访问器

用于查询与写入系统操作记录，支持变更追踪与问题回溯。

核心功能：
  - list_entity_history: 获取实体变更历史
  - list_failed_operations: 获取失败操作记录
  - list_user_actions: 获取用户操作记录
  - create_audit: 创建审计日志

说明：
  审计日志为不可变记录，仅支持追加写入，不支持更新操作。

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.audit import AuditRepository

  async with UnitOfWork() as uow:
      repo = AuditRepository(uow.session)

      audit = await repo.create_audit(
          audit_id="aud_a1b2c3d4",
          action="model.register",
          resource="model",
          operation="register",
          target_type="model",
          target_id="mdl_a1b2c3d4",
          source="http",
          user="admin",
          ip="127.0.0.1",
          after={"name": "scorecard"}
      )
"""

from datetime import datetime, timezone
from sqlalchemy import select

from datamind.db.models.audit import Audit
from datamind.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """审计日志访问器"""

    async def list_entity_history(self, target_type: str, target_id: str) -> list[Audit]:
        """获取某个实体的变更历史

        参数：
            target_type: 目标类型
            target_id: 目标 ID

        返回：
            审计记录列表，按发生时间升序排列
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

    async def list_failed_operations(self, limit: int = 100) -> list[Audit]:
        """获取失败操作记录

        参数：
            limit: 返回数量限制

        返回：
            失败操作记录列表，按发生时间倒序排列
        """
        stmt = (
            select(Audit)
            .where(Audit.status == "failed")
            .order_by(Audit.occurred_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_user_actions(self, user: str, limit: int = 100) -> list[Audit]:
        """获取用户操作记录

        参数：
            user: 用户名
            limit: 返回数量限制

        返回：
            用户操作记录列表，按发生时间倒序排列
        """
        stmt = (
            select(Audit)
            .where(Audit.user == user)
            .order_by(Audit.occurred_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_audit(
        self,
        *,
        audit_id: str,
        action: str,
        resource: str,
        operation: str,
        target_type: str,
        target_id: str,
        source: str,
        trace_id: str | None = None,
        request_id: str | None = None,
        user: str | None = None,
        ip: str | None = None,
        status: str = "success",
        error: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        context: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> Audit:
        """创建审计日志

        参数：
            audit_id: 审计记录 ID
            action: 操作类型
            resource: 资源类型
            operation: 操作名称
            target_type: 目标类型
            target_id: 目标 ID
            source: 来源类型
            trace_id: 链路追踪 ID（可选）
            request_id: 请求 ID（可选）
            user: 操作用户（可选）
            ip: 客户端IP（可选）
            status: 操作状态
            error: 错误信息（可选）
            before: 变更前数据（可选）
            after: 变更后数据（可选）
            context: 操作上下文（可选）
            occurred_at: 发生时间（可选）

        返回：
            创建后的审计记录对象
        """
        obj = Audit(
            audit_id=audit_id,
            action=action,
            resource=resource,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            source=source,
            trace_id=trace_id,
            request_id=request_id,
            user=user,
            ip=ip,
            status=status,
            error=error,
            before=before,
            after=after,
            context=context,
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )

        self.add(obj)
        return obj