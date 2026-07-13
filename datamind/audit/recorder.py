# datamind/audit/recorder.py

"""审计记录器

统一封装审计事件记录，自动注入上下文信息并交由审计服务持久化。

核心功能：
  - AuditRecorder: 审计记录器，自动注入上下文信息

使用示例：
  from datamind.audit.recorder import AuditRecorder

  recorder = AuditRecorder()
  await recorder.record(
      action="model.register",
      target_type="model",
      target_id="mdl_0123456789abcdef",
      after={"name": "scorecard"},
  )
"""

from typing import Any

import structlog

from datamind.audit.event import AuditEvent
from datamind.audit.policy import AuditFailureMode
from datamind.audit.sanitizer import (
    sanitize_audit_mapping,
    sanitize_audit_value,
)
from datamind.audit.service import (
    AuditResult,
    AuditService,
)
from datamind.config import get_settings
from datamind.config.audit import AuditConfig
from datamind.context import get_context
from datamind.context.keys import (
    HOSTNAME,
    IP,
    REQUEST_ID,
    SOURCE,
    TRACE_ID,
    USER,
)

logger = structlog.get_logger(__name__)


class AuditRecorder:
    """审计记录器"""

    def __init__(
            self,
            *,
            service: AuditService | None = None,
    ) -> None:
        self._config: AuditConfig = get_settings().audit
        self._context = get_context
        self._service = service or AuditService(
            config=self._config
        )

    @property
    def enabled(self) -> bool:
        """是否启用审计组件"""
        return self._config.enabled

    @property
    def failure_mode(self) -> AuditFailureMode:
        """获取默认审计失败策略"""
        return AuditFailureMode(
            self._config.failure_mode
        )

    async def record(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        status: str = "success",
        error: str | None = None,
        before: Any | None = None,
        after: Any | None = None,
        context: dict[str, Any] | None = None,
        failure_mode: AuditFailureMode | None = None,
    ) -> AuditResult | None:
        """记录审计事件

        参数：
            action: 操作类型，格式为 resource.operation
            target_type: 目标类型
            target_id: 目标 ID
            status: 操作状态
            error: 错误信息
            before: 变更前数据
            after: 变更后数据
            context: 操作上下文

        异常：
            AuditWriteError: Fail-closed 模式下审计事件写入失败
        """
        if not self.enabled:
            return None

        ctx = dict(self._context())

        if context:
            ctx.update(context)

        trace_id = ctx.get(TRACE_ID)
        request_id = ctx.get(REQUEST_ID)
        source = ctx.get(SOURCE)
        user = ctx.get(USER)
        ip = ctx.get(IP)
        hostname = ctx.get(HOSTNAME)

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
            error=(
                sanitize_audit_value(error)
                if error is not None
                else None
            ),
            trace_id=trace_id,
            request_id=request_id,
            source=source,
            user=user,
            ip=ip,
            hostname=hostname,
            before=sanitize_audit_value(before),
            after=sanitize_audit_value(after),
            context=sanitize_audit_mapping(ctx),
        )

        logger.debug(
            "审计事件创建",
            audit_id=event.audit_id,
            action=event.action,
            target_id=event.target_id,
            status=event.status,
        )

        return await self._service.record(
            event,
            failure_mode=failure_mode,
        )
