# datamind/audit/recorder.py

"""审计记录器

统一封装审计事件记录，自动注入上下文信息并分发到队列。

核心功能：
  - AuditRecorder: 审计记录器，自动注入上下文信息

使用示例：
  from datamind.audit.recorder import AuditRecorder

  recorder = AuditRecorder()
  await recorder.record(
      action="model.register",
      target_type="model",
      target_id="mdl_001",
      after={"name": "scorecard"}
  )
"""

import structlog
from typing import Optional, Dict

from datamind.context import get_context
from datamind.context.keys import TRACE_ID, REQUEST_ID, SOURCE, USER, IP
from datamind.audit.event import AuditEvent
from datamind.audit.dispatcher import dispatch
from datamind.audit.exceptions import AuditDispatchError

logger = structlog.get_logger(__name__)

class AuditRecorder:
    """审计记录器"""

    def __init__(self):
        self._context = get_context

    async def record(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        status: str = "success",
        error: Optional[str] = None,
        before: Optional[Dict] = None,
        after: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ):
        """记录审计事件

        参数：
            action: 操作类型，格式为 resource.operation
            target_type: 目标类型
            target_id: 目标ID
            status: 操作状态
            error: 错误信息
            before: 变更前数据
            after: 变更后数据
            context: 操作上下文
        """

        ctx = dict(self._context())

        if context:
            ctx.update(context)

        trace_id = ctx.get(TRACE_ID)
        request_id = ctx.get(REQUEST_ID)
        source = ctx.get(SOURCE)
        user = ctx.get(USER)
        ip = ctx.get(IP)

        if "." in action:
            resource, operation = action.split(".", 1)
        else:
            resource, operation = action, ""

        event = AuditEvent(
            action=action,
            resource=resource,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            status=status,
            error=error,
            trace_id=trace_id,
            request_id=request_id,
            source=source,
            user=user,
            ip=ip,
            before=before,
            after=after,
            context=ctx,
        )

        logger.debug(
            "审计事件创建",
            action=action,
            target_id=target_id,
            status=status,
        )

        try:
            await dispatch(event)
        except AuditDispatchError:
            raise
        except Exception as e:
            logger.error(
                "审计事件分发失败",
                error=str(e),
                action=action,
                target_id=target_id,
                trace_id=trace_id,
                exc_info=True,
            )