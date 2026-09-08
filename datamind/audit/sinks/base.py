"""审计存储端协议"""

from typing import Protocol

from datamind.audit.event import AuditEvent
from datamind.db.models.audit import Audit


class AuditSink(Protocol):
    """审计事件持久化协议"""

    async def write(
            self,
            event: AuditEvent,
    ) -> Audit:
        """持久化审计事件"""
        ...
