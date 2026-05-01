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
      trace_id="trace-123",
      request_id="req-456",
      source="system",
      user="admin",
      ip="192.168.1.100",
      before=None,
      after={"name": "scorecard"},
      context={}
  )
"""

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class AuditEvent:
    """审计事件

    属性：
        action: 操作类型，格式为 resource.operation
        resource: 资源类型
        operation: 操作名称
        target_type: 目标类型
        target_id: 目标ID
        status: 操作状态
        error: 错误信息
        trace_id: 链路追踪ID
        request_id: 请求ID
        source: 来源类型
        user: 操作用户
        ip: 客户端IP
        before: 变更前数据
        after: 变更后数据
        context: 操作上下文
    """
    action: str
    resource: str
    operation: str
    target_type: str
    target_id: str

    status: str
    error: Optional[str]

    trace_id: Optional[str]
    request_id: Optional[str]
    source: Optional[str]
    user: Optional[str]
    ip: Optional[str]

    before: Optional[Dict]
    after: Optional[Dict]
    context: Optional[Dict]

    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))