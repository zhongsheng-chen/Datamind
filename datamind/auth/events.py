"""认证安全事件记录.

统一记录认证边界产生的结构化日志和持久化审计事件。

核心功能：
  - record_authentication_event: 记录不包含认证秘密的认证事件
"""

from collections.abc import Mapping

from structlog.typing import FilteringBoundLogger

from datamind.audit.enums import AuditStatus
from datamind.audit.recorder import AuditRecorder


async def record_authentication_event(
        *,
        logger: FilteringBoundLogger,
        recorder: AuditRecorder,
        channel: str,
        action: str,
        actor_username: str,
        target_id: str,
        successful: bool,
        status_code: int,
        context: Mapping[str, object],
        attempted_username: str | None = None,
        error: str | None = None,
        details: Mapping[str, object] | None = None,
) -> None:
    """记录不包含密码或令牌的认证事件."""
    status = (
        AuditStatus.SUCCESS
        if successful
        else AuditStatus.FAILED
    )
    event_context = dict(context)
    event_context["user"] = actor_username

    if attempted_username is not None:
        event_context["attempted_username"] = attempted_username

    event_details = dict(details or {})
    log = (
        logger.info
        if successful
        else (
            logger.error
            if status_code >= 500
            else logger.warning
        )
    )
    operation = action.partition(".")[2]
    operation_label = {
        "login": "登录",
        "logout": "退出登录",
    }.get(
        operation,
        operation,
    )
    log(
        (
            f"{channel}{operation_label}成功"
            if successful
            else f"{channel}{operation_label}失败"
        ),
        action=action,
        status=str(status),
        status_code=status_code,
        **event_context,
        **event_details,
    )
    await recorder.record(
        action=action,
        target_type="user",
        target_id=target_id,
        status=str(status),
        error=error,
        after={
            "status_code": status_code,
            **event_details,
        },
        context=event_context,
    )


__all__ = [
    "record_authentication_event",
]
