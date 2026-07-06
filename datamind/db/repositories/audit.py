# datamind/db/repositories/audit.py

"""审计日志仓储

用于查询与写入系统操作记录，支持变更追踪与问题回溯。

核心功能：
  - list_audits: 获取审计日志列表
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

      audit = repo.create_audit(
          audit_id="aud_a1b2c3d4",
          action="model.register",
          resource="model",
          operation="register",
          target_type="model",
          target_id="mdl_a1b2c3d4",
          source="http",
          user="admin",
          ip="192.168.1.100",
          hostname="client",
          after={"name": "scorecard"}
      )
"""

from datetime import datetime, timezone

from sqlalchemy import select

from datamind.db.models.audit import Audit
from datamind.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """审计日志仓储"""

    async def list_audits(
            self,
            *,
            limit: int | None = None,
            offset: int | None = None,
            order_desc: bool = True,
            **filters,
    ) -> list[Audit]:
        """获取审计日志列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            order_desc: 是否按发生时间倒序排列
            **filters: 过滤条件
                支持字段：
                    action
                    resource
                    operation
                    target_type
                    target_id
                    source
                    trace_id
                    request_id
                    user
                    ip
                    hostname
                    status

        返回：
            审计记录列表，按发生时间排序
        """
        stmt = select(Audit)

        if filters:
            stmt = stmt.filter_by(**filters)

        if order_desc:
            stmt = stmt.order_by(Audit.occurred_at.desc())
        else:
            stmt = stmt.order_by(Audit.occurred_at.asc())

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_entity_history(
            self,
            target_type: str,
            target_id: str,
    ) -> list[Audit]:
        """获取某个实体的变更历史

        参数：
            target_type: 目标类型
            target_id: 目标 ID

        返回：
            审计记录列表，按发生时间升序排列
        """
        filters = {
            "target_type": target_type,
            "target_id": target_id,
        }

        return await self.list_audits(
            order_desc=False,
            **filters,
        )

    async def list_failed_operations(
            self,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Audit]:
        """获取失败操作记录

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            失败操作记录列表，按发生时间倒序排列
        """
        filters = {
            "status": "failed",
        }

        return await self.list_audits(
            limit=limit,
            offset=offset,
            **filters,
        )

    async def list_user_actions(
            self,
            user: str,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Audit]:
        """获取用户操作记录

        参数：
            user: 用户名
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            用户操作记录列表，按发生时间倒序排列
        """
        filters = {
            "user": user,
        }

        return await self.list_audits(
            limit=limit,
            offset=offset,
            **filters,
        )

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
            hostname: str | None = None,
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
            ip: 客户端 IP 地址（可选）
            hostname: 客户端主机名称（可选）
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
            hostname=hostname,
            status=status,
            error=error,
            before=before,
            after=after,
            context=context,
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )

        self.add(obj)

        return obj
