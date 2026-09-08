"""数据库审计存储端

核心功能：
  - DatabaseAuditSink: 使用数据库工作单元幂等写入审计事件
"""

from sqlalchemy.exc import IntegrityError

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.audit.event import AuditEvent
from datamind.db.core.uow import UnitOfWork
from datamind.db.models.audit import Audit


class DatabaseAuditSink:
    """数据库审计存储端"""

    async def write(
            self,
            event: AuditEvent,
    ) -> Audit:
        """幂等写入审计事件"""
        try:
            return await self._write_once(
                event
            )
        except IntegrityError:
            existing = await self._find_existing(
                event.audit_id
            )

            if existing is not None:
                return existing

            raise

    @staticmethod
    async def _find_existing(
            audit_id: str,
    ) -> Audit | None:
        """查找已写入的审计事件"""
        from datamind.db.repositories.audit import AuditRepository

        async with UnitOfWork() as uow:
            existing = await AuditRepository(
                uow.session
            ).get_by_audit_id(
                audit_id
            )

        return existing

    @staticmethod
    async def _write_once(
            event: AuditEvent,
    ) -> Audit:
        """写入单个审计事件"""
        from datamind.db.repositories.audit import AuditRepository

        async with UnitOfWork() as uow:
            repository = AuditRepository(
                uow.session
            )
            existing = await repository.get_by_audit_id(
                event.audit_id
            )
            source = AuditSource(
                event.source or AuditSource.SYSTEM
            )
            status = AuditStatus(
                event.status
            )
            audit: Audit = (
                existing
                if existing is not None
                else repository.create_audit(
                    audit_id=event.audit_id,
                    action=event.action,
                    resource=event.resource,
                    operation=event.operation,
                    target_type=event.target_type,
                    target_id=event.target_id,
                    trace_id=event.trace_id,
                    request_id=event.request_id,
                    source=source,
                    user=event.user,
                    ip=event.ip,
                    hostname=event.hostname,
                    status=status,
                    error=event.error,
                    before=event.before,
                    after=event.after,
                    context=event.context,
                    occurred_at=event.occurred_at,
                )
            )

        return audit
