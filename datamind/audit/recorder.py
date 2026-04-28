"""审计记录器

统一封装审计日志写入，自动注入上下文信息。

核心功能：
  - AuditRecorder: 审计记录器，自动注入上下文信息

使用示例：
  from datamind.audit.recorder import AuditRecorder

  recorder = AuditRecorder(writer)
  await recorder.record(
      action="model.register",
      target_type="model",
      target_id="mdl_001",
      after={"name": "scorecard"}
  )
"""

from typing import Optional, Dict, Any

from datamind.context import get_context
from datamind.context.keys import USER, IP, TRACE_ID, REQUEST_ID
from datamind.logging import get_logger

logger = get_logger(__name__)


class AuditRecorder:
    """审计记录器"""

    def __init__(self, writer):
        """初始化审计记录器

        参数：
            writer: AuditWriter 实例
        """
        self.writer = writer

    def _parse_action(self, action: str):
        """解析 action -> resource / operation"""
        parts = action.split(".", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return action, ""

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
        """记录审计日志"""

        global_context = get_context()
        merged_context: Dict[str, Any] = dict(global_context)

        if context:
            merged_context.update(context)

        trace_id = merged_context.get(TRACE_ID)
        request_id = merged_context.get(REQUEST_ID)
        user = merged_context.get(USER)
        ip = merged_context.get(IP)

        resource, operation = self._parse_action(action)

        try:
            logger.debug(
                "审计记录写入",
                action=action,
                target_type=target_type,
                target_id=target_id,
                trace_id=trace_id,
                request_id=request_id,
                user=user,
                ip=ip,
                status=status,
            )

            return await self.writer.write(
                action=action,
                resource=resource,
                operation=operation,
                target_type=target_type,
                target_id=target_id,
                trace_id=trace_id,
                request_id=request_id,
                user=user,
                ip=ip,
                status=status,
                error=error,
                before=before,
                after=after,
                context=merged_context,
            )

        except Exception as e:
            logger.error(
                "审计记录写入失败",
                action=action,
                target_type=target_type,
                target_id=target_id,
                trace_id=trace_id,
                request_id=request_id,
                user=user,
                ip=ip,
                status="failed",
                error=str(e),
                exc_info=True,
            )

            return await self.writer.write(
                action=action,
                resource=resource,
                operation=operation,
                target_type=target_type,
                target_id=target_id,
                trace_id=trace_id,
                request_id=request_id,
                user=user,
                ip=ip,
                status="failed",
                error=str(e),
                before=before,
                after=after,
                context=merged_context,
            )