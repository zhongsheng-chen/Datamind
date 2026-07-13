# datamind/audit/event.py

"""审计事件定义

定义审计日志的数据结构。

核心功能：
  - AuditEvent: 审计事件数据类

使用示例：
  from datamind.audit.event import AuditEvent

  event = AuditEvent(
      action="model.register",
      resource="model",
      operation="register",
      target_type="model",
      target_id="mdl_001",
      status="success",
      error=None,
      trace_id="0123456789abcdef",
      request_id="req_0123456789abcdef",
      source="http",
      user="admin",
      ip="192.168.1.100",
      hostname="client",
      before=None,
      after={"name": "scorecard"},
      context={},
  )

  print(event.audit_id)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.audit.errors import AuditValidationError
from datamind.utils.generator import generate_random_id


@dataclass(frozen=True)
class AuditEvent:
    """审计事件

    属性：
        action: 操作类型，格式为 resource.operation
        resource: 资源类型
        operation: 操作名称
        target_type: 目标类型
        target_id: 目标 ID
        status: 操作状态
        error: 错误信息
        trace_id: 链路追踪 ID
        request_id: 请求 ID
        source: 来源类型
        user: 操作用户
        ip: 客户端 IP 地址
        hostname: 客户端主机名称
        before: 变更前数据
        after: 变更后数据
        context: 操作上下文
        audit_id: 审计事件 ID
        occurred_at: 事件发生时间（UTC）
    """

    action: str
    resource: str
    operation: str
    target_type: str
    target_id: str

    status: AuditStatus | str
    error: str | None

    trace_id: str | None
    request_id: str | None
    source: AuditSource | str | None
    user: str | None
    ip: str | None
    hostname: str | None

    before: Any | None
    after: Any | None
    context: dict[str, Any] | None

    audit_id: str = field(
        default_factory=lambda: generate_random_id(
            prefix="aud"
        )
    )
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        """校验并规范化审计事件"""
        required_fields = {
            "audit_id": (self.audit_id, 64),
            "action": (self.action, 64),
            "resource": (self.resource, 64),
            "operation": (self.operation, 64),
            "target_type": (self.target_type, 64),
            "target_id": (self.target_id, 64),
        }

        for name, (value, max_length) in required_fields.items():
            if not value or not value.strip():
                raise AuditValidationError(
                    f"{name} 不能为空"
                )

            if len(value) > max_length:
                raise AuditValidationError(
                    f"{name} 长度不能超过 {max_length}"
                )

        optional_fields = {
            "trace_id": (self.trace_id, 64),
            "request_id": (self.request_id, 64),
            "user": (self.user, 64),
            "ip": (self.ip, 64),
            "hostname": (self.hostname, 128),
        }

        for name, (value, max_length) in optional_fields.items():
            if value is not None and len(value) > max_length:
                raise AuditValidationError(
                    f"{name} 长度不能超过 {max_length}"
                )

        if self.action != f"{self.resource}.{self.operation}":
            raise AuditValidationError(
                "action 必须与 resource 和 operation 一致"
            )

        if self.occurred_at.tzinfo is None:
            raise AuditValidationError(
                "occurred_at 必须包含时区"
            )

        try:
            status = AuditStatus(
                self.status
            )
            source = AuditSource(
                self.source or AuditSource.SYSTEM
            )
        except ValueError as exc:
            raise AuditValidationError(
                f"审计事件枚举值无效：{exc}"
            ) from exc

        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "source",
            source,
        )
