"""审计存储端

核心功能：
  - AuditSink: 审计存储端协议
  - DatabaseAuditSink: 数据库审计存储端
"""

from datamind.audit.sinks.base import AuditSink
from datamind.audit.sinks.database import DatabaseAuditSink

__all__ = [
    "AuditSink",
    "DatabaseAuditSink",
]
