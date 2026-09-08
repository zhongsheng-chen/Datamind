"""审计日志仓储

用于查询与写入系统操作记录，
支持变更追踪、问题排查和审计分析。

核心功能：
  - list_audits: 获取审计日志列表
  - list_entity_history: 获取实体变更历史
  - list_failed_operations: 获取失败操作记录
  - list_user_actions: 获取用户操作记录
  - get_by_audit_id: 按审计 ID 获取记录
  - create_audit: 创建审计日志

说明：
  审计日志为不可变记录，仅支持追加写入，不支持更新操作。

使用示例：
  from datamind.audit.enums import AuditSource
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.audit import AuditRepository

  async with UnitOfWork() as uow:
      repo = AuditRepository(
          uow.session
      )

      audit = repo.create_audit(
          audit_id="aud_0123456789abcdef",
          action="model.register",
          resource="model",
          operation="register",
          target_type="model",
          target_id="mdl_0123456789abcdef",
          source=AuditSource.CLI,
          trace_id="0123456789abcdef0123456789abcdef",
          request_id="req_0123456789abcdef",
          user="admin",
          ip="192.168.1.100",
          hostname="client",
          after={
              "name": "scorecard",
          },
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.db.models.audit import Audit
from datamind.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """审计日志仓储"""

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

    async def list_audits(
            self,
            *,
            audit_id: str | None = None,
            action: str | None = None,
            resource: str | None = None,
            operation: str | None = None,
            target_type: str | None = None,
            target_id: str | None = None,
            source: AuditSource | None = None,
            trace_id: str | None = None,
            request_id: str | None = None,
            user: str | None = None,
            ip: str | None = None,
            hostname: str | None = None,
            status: AuditStatus | None = None,
            limit: int | None = None,
            offset: int | None = None,
            order_desc: bool = True,
    ) -> list[Audit]:
        """获取审计日志列表

        参数：
            audit_id: 审计 ID（可选）
            action: 操作类型（可选）
            resource: 资源类型（可选）
            operation: 操作名称（可选）
            target_type: 目标类型（可选）
            target_id: 目标 ID（可选）
            source: 来源类型（可选）
            trace_id: 链路追踪 ID（可选）
            request_id: 请求 ID（可选）
            user: 操作用户（可选）
            ip: 客户端 IP 地址（可选）
            hostname: 客户端主机名称（可选）
            status: 操作状态（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            order_desc: 是否按发生时间倒序排列

        返回：
            审计记录列表，按发生时间排序

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Audit
        )

        if audit_id is not None:
            stmt = stmt.where(
                Audit.audit_id
                == audit_id
            )

        if action is not None:
            stmt = stmt.where(
                Audit.action
                == action
            )

        if resource is not None:
            stmt = stmt.where(
                Audit.resource
                == resource
            )

        if operation is not None:
            stmt = stmt.where(
                Audit.operation
                == operation
            )

        if target_type is not None:
            stmt = stmt.where(
                Audit.target_type
                == target_type
            )

        if target_id is not None:
            stmt = stmt.where(
                Audit.target_id
                == target_id
            )

        if source is not None:
            stmt = stmt.where(
                Audit.source
                == str(
                    source
                )
            )

        if trace_id is not None:
            stmt = stmt.where(
                Audit.trace_id
                == trace_id
            )

        if request_id is not None:
            stmt = stmt.where(
                Audit.request_id
                == request_id
            )

        if user is not None:
            stmt = stmt.where(
                Audit.user
                == user
            )

        if ip is not None:
            stmt = stmt.where(
                Audit.ip
                == ip
            )

        if hostname is not None:
            stmt = stmt.where(
                Audit.hostname
                == hostname
            )

        if status is not None:
            stmt = stmt.where(
                Audit.status
                == str(
                    status
                )
            )

        if order_desc:
            stmt = stmt.order_by(
                Audit.occurred_at.desc(),
                Audit.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(
                Audit.occurred_at.asc(),
                Audit.created_at.asc(),
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

    async def list_entity_history(
            self,
            target_type: str,
            target_id: str,
    ) -> list[Audit]:
        """获取实体变更历史

        参数：
            target_type: 目标类型
            target_id: 目标 ID

        返回：
            审计记录列表，按发生时间和创建时间升序排列
        """
        return await self.list_audits(
            target_type=target_type,
            target_id=target_id,
            order_desc=False,
        )

    async def get_by_audit_id(
            self,
            audit_id: str,
    ) -> Audit | None:
        """按唯一审计 ID 获取记录。"""
        result = await self.session.execute(
            select(Audit).where(
                Audit.audit_id == audit_id
            )
        )
        return result.scalar_one_or_none()

    async def list_failed_operations(
            self,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Audit]:
        """获取失败操作记录

        参数：
            limit: 返回数量限制，默认 100
            offset: 分页偏移（可选）

        返回：
            失败操作记录列表，按发生时间倒序排列
        """
        return await self.list_audits(
            status=AuditStatus.FAILED,
            limit=limit,
            offset=offset,
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
            limit: 返回数量限制，默认 100
            offset: 分页偏移（可选）

        返回：
            用户操作记录列表，按发生时间倒序排列
        """
        return await self.list_audits(
            user=user,
            limit=limit,
            offset=offset,
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
            source: AuditSource,
            trace_id: str | None = None,
            request_id: str | None = None,
            user: str | None = None,
            ip: str | None = None,
            hostname: str | None = None,
            status: AuditStatus = AuditStatus.SUCCESS,
            error: str | None = None,
            before: dict | None = None,
            after: dict | None = None,
            context: dict | None = None,
            occurred_at: datetime | None = None,
    ) -> Audit:
        """创建审计日志

        参数：
            audit_id: 审计 ID
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
            status: 操作状态，默认 success
            error: 错误信息（可选）
            before: 变更前数据（可选）
            after: 变更后数据（可选）
            context: 操作上下文（可选）
            occurred_at: 操作发生时间（可选）

        返回：
            创建后的审计记录对象

        """
        new_audit = Audit(
            audit_id=audit_id,
            action=action,
            resource=resource,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            source=str(
                source
            ),
            status=str(
                status
            ),
            before=before,
            after=after,
            context=context,
            occurred_at=(
                occurred_at
                if occurred_at is not None
                else datetime.now(
                    timezone.utc
                )
            ),
        )

        if trace_id is not None:
            new_audit.trace_id = trace_id

        if request_id is not None:
            new_audit.request_id = request_id

        if user is not None:
            new_audit.user = user

        if ip is not None:
            new_audit.ip = ip

        if hostname is not None:
            new_audit.hostname = hostname

        if error is not None:
            new_audit.error = error

        self.add(
            new_audit
        )

        return new_audit
