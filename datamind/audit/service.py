# datamind/audit/service.py

"""审计服务

统一执行审计持久化、瞬时故障重试和失败策略。

核心功能：
  - AuditResult: 审计记录结果
  - AuditService: 审计事件服务
"""

import asyncio
from dataclasses import dataclass

import structlog
from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
    TimeoutError as SQLAlchemyTimeoutError,
)

from datamind.audit.errors import AuditWriteError
from datamind.audit.event import AuditEvent
from datamind.audit.policy import AuditFailureMode
from datamind.audit.sinks import (
    AuditSink,
    DatabaseAuditSink,
)
from datamind.config import get_settings
from datamind.config.audit import AuditConfig

logger = structlog.get_logger(__name__)

_TRANSIENT_ERRORS = (
    InterfaceError,
    OperationalError,
    SQLAlchemyTimeoutError,
)


@dataclass(frozen=True)
class AuditResult:
    """审计记录结果"""

    audit_id: str
    recorded: bool
    error: str | None = None


class AuditService:
    """审计事件服务"""

    def __init__(
            self,
            *,
            sink: AuditSink | None = None,
            config: AuditConfig | None = None,
    ) -> None:
        self._sink = sink or DatabaseAuditSink()
        self._config = config or get_settings().audit

    async def record(
            self,
            event: AuditEvent,
            *,
            failure_mode: AuditFailureMode | None = None,
    ) -> AuditResult:
        """记录审计事件"""
        if not self._config.enabled:
            return AuditResult(
                audit_id=event.audit_id,
                recorded=False,
            )

        mode = failure_mode or AuditFailureMode(
            self._config.failure_mode
        )

        for attempt in range(
                1,
                self._config.max_retries + 1,
        ):
            try:
                await self._sink.write(
                    event
                )

                return AuditResult(
                    audit_id=event.audit_id,
                    recorded=True,
                )
            except Exception as exc:
                transient = isinstance(
                    exc,
                    _TRANSIENT_ERRORS,
                )

                if (
                        transient
                        and attempt < self._config.max_retries
                ):
                    await asyncio.sleep(
                        self._config.retry_base_delay
                        * (2 ** (attempt - 1))
                    )
                    continue

                logger.error(
                    "审计事件写入失败",
                    error=str(exc),
                    audit_id=event.audit_id,
                    action=event.action,
                    target_id=event.target_id,
                    attempt=attempt,
                    transient=transient,
                    exc_info=True,
                )

                if mode is AuditFailureMode.CLOSED:
                    raise AuditWriteError(
                        f"审计事件写入失败：{exc}"
                    ) from exc

                return AuditResult(
                    audit_id=event.audit_id,
                    recorded=False,
                    error=str(exc),
                )

        raise RuntimeError(
            "审计重试流程异常结束"
        )
