# datamind/audit/writer.py

"""审计事件写入器

从队列消费审计事件并写入数据库，使用独立事务。

核心功能：
  - AuditWriter: 审计事件写入器

使用示例：
  from datamind.audit.writer import AuditWriter

  await AuditWriter.write(event)
"""

import structlog
from datetime import datetime, timezone
from typing import Optional

from datamind.db.core.session import get_session_factory
from datamind.db.models.audit import Audit

logger = structlog.get_logger(__name__)


class AuditWriter:
    """审计日志写入器"""

    @classmethod
    async def write(cls, event) -> Optional[Audit]:
        """写入审计事件

        参数：
            event: AuditEvent 实例

        返回：
            写入成功的审计记录对象，失败时返回 None
        """
        SessionFactory = get_session_factory()
        session = SessionFactory()

        try:
            obj = Audit(
                action=event.action,
                resource=event.resource,
                operation=event.operation,
                target_type=event.target_type,
                target_id=event.target_id,
                trace_id=event.trace_id,
                request_id=event.request_id,
                source=event.source,
                user=event.user,
                ip=event.ip,
                status=event.status,
                error=event.error,
                before=event.before,
                after=event.after,
                context=event.context,
                occurred_at=event.occurred_at or datetime.now(timezone.utc),
            )

            session.add(obj)
            await session.commit()
            return obj

        except Exception as e:
            await session.rollback()

            logger.error(
                "审计写入失败",
                error=str(e),
                action=event.action,
                target_id=event.target_id,
                trace_id=event.trace_id,
                exc_info=True,
            )

            return None

        finally:
            await session.close()