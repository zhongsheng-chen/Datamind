# datamind/audit/__init__.py

"""审计模块

提供控制平面事件溯源能力，记录所有系统变更行为。

核心功能：
  - AuditRecorder: 审计记录器
  - audit_action: 审计装饰器
  - audit_context: 审计上下文管理器

使用示例：
  from datamind.audit import AuditRecorder, audit_context

  with audit_context(user_id="admin", ip="192.168.1.100"):
      recorder = AuditRecorder(session)
      recorder.record(
          action="deployment.deploy",
          target_type="deployment",
          target_id="dep_001",
          after={"status": "active"}
      )
"""

from datamind.audit.context import audit_context, get_context, set_context, clear_context
from datamind.audit.recorder import AuditRecorder
from datamind.audit.decorator import audit_action

__all__ = [
    "audit_context",
    "get_context",
    "set_context",
    "clear_context",
    "AuditRecorder",
    "audit_action",
]