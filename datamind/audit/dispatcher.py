# datamind/audit/dispatcher.py

"""审计事件分发器

提供异步队列的事件分发能力，用于解耦审计事件的生产和消费。

核心功能：
  - dispatch: 发送审计事件到队列
  - get_queue: 获取审计事件队列

使用示例：
  from datamind.audit.dispatcher import dispatch, get_queue
  from datamind.audit.event import AuditEvent

  event = AuditEvent(...)
  await dispatch(event)

  queue = get_queue()
  event = await queue.get()
"""

import asyncio
import structlog

from datamind.audit.event import AuditEvent
from datamind.audit.exceptions import AuditDispatchError

logger = structlog.get_logger(__name__)

_queue: asyncio.Queue[AuditEvent] = asyncio.Queue()


async def dispatch(event: AuditEvent):
    """发送审计事件

    参数：
        event: 审计事件对象
    """
    try:
        await _queue.put(event)

        logger.debug(
            "审计事件入队",
            action=event.action,
            target_id=event.target_id,
            status=event.status,
            trace_id=event.trace_id,
            request_id=event.request_id,
            source=event.source,
            user=event.user,
            ip=event.ip,
        )

    except Exception as e:
        raise AuditDispatchError(f"审计事件入队失败: {str(e)}")


def get_queue() -> asyncio.Queue:
    """获取审计事件队列

    返回：
        审计事件队列
    """
    return _queue