# datamind/db/events.py

"""数据库变更事件

负责在业务数据发生变化时写入控制台事件，
并在事务提交后通知实时事件监听器。

核心功能：
  - register_events: 注册业务模型变更监听器

使用示例：
  import datamind.db

  # 导入数据库模块时自动注册变更监听器。
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import (
    event,
    insert,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper

from datamind.db.models import (
    Audit,
    Decision,
    Deployment,
    Execution,
    Experiment,
    Metadata,
    OutboxEvent,
    Request,
    Routing,
    Runtime,
    Variant,
    Version,
)


EventListener = Callable[
    [Mapper[Any], Connection, Any],
    None,
]

_CHANNEL = "datamind_console_events"
_REGISTERED = False


def _write_event(
        connection: Connection,
        *,
        topic: str,
        resource_id: str | None,
        action: str,
) -> None:
    """在当前事务中写入控制台变更事件并发送通知"""
    stmt = insert(
        OutboxEvent
    ).values(
        topic=topic,
        resource_id=resource_id,
        action=action,
    ).returning(
        OutboxEvent.event_id
    )
    event_id = connection.execute(
        stmt
    ).scalar_one()

    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "SELECT pg_notify(:channel, :event_id)"
            ),
            {
                "channel": _CHANNEL,
                "event_id": str(
                    event_id
                ),
            },
        )


def _create_listener(
        *,
        topic: str,
        identifier: str,
        action: str,
) -> EventListener:
    """创建业务模型变更监听器"""
    def listener(
            _mapper: Mapper[Any],
            connection: Connection,
            target: Any,
    ) -> None:
        resource_id = getattr(
            target,
            identifier,
            None,
        )
        _write_event(
            connection,
            topic=topic,
            resource_id=(
                resource_id
                if isinstance(
                    resource_id,
                    str,
                )
                else None
            ),
            action=action,
        )

    return listener


def register_events() -> None:
    """注册业务模型变更监听器"""
    global _REGISTERED

    if _REGISTERED:
        return

    registrations = (
        (Metadata, "models", "model_id"),
        (Version, "versions", "version_id"),
        (Deployment, "deployments", "deployment_id"),
        (Routing, "routings", "routing_id"),
        (Runtime, "runtimes", "runtime_id"),
        (Request, "requests", "request_id"),
        (Decision, "decisions", "decision_id"),
        (Execution, "executions", "execution_id"),
        (Experiment, "experiments", "experiment_id"),
        (Variant, "variants", "variant_id"),
        (Audit, "audits", "audit_id"),
    )

    for model, topic, identifier in registrations:
        for operation, action in (
                ("after_insert", "insert"),
                ("after_update", "update"),
                ("after_delete", "delete"),
        ):
            event.listen(
                model,
                operation,
                _create_listener(
                    topic=topic,
                    identifier=identifier,
                    action=action,
                ),
            )

    _REGISTERED = True


register_events()
