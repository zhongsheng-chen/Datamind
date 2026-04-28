# datamind/audit/recorder.py

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
        """记录审计日志

        参数：
            action: 操作类型（resource.verb 格式）
            target_type: 目标类型
            target_id: 目标ID
            status: 操作状态
            error: 错误信息
            before: 变更前数据（可选）
            after: 变更后数据（可选）
            context: 操作上下文（可选）

        返回：
            审计记录对象
        """
        global_context = get_context()
        merged_context: Dict[str, Any] = dict(global_context)

        if context:
            merged_context.update(context)

        trace_id = merged_context.get(TRACE_ID)
        request_id = merged_context.get(REQUEST_ID)
        user = merged_context.get(USER)
        ip = merged_context.get(IP)

        if "." in action:
            resource, operation = action.split(".", 1)
        else:
            resource, operation = action, ""

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