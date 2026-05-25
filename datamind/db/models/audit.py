# datamind/db/models/audit.py

"""审计日志表

记录系统控制平面的所有变更行为，提供变更追溯和审计能力。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表"""

    __tablename__ = "audit"

    __table_args__ = (
        Index("idx_audit_target_id_occurred_at", "target_type", "target_id", "occurred_at"),
        Index("idx_audit_trace_id_occurred_at", "trace_id", "occurred_at",
              postgresql_where=text("trace_id IS NOT NULL")),
        Index("idx_audit_request_id_occurred_at", "request_id", "occurred_at",
              postgresql_where=text("request_id IS NOT NULL")),
        Index("idx_audit_user_occurred_at", "user", "occurred_at"),
        Index("idx_audit_target_type_occurred_at", "target_type", "occurred_at"),
        Index("idx_audit_failed_occurred_at", "occurred_at",
              postgresql_where=text("status = 'failed'")),
        Index("idx_audit_source_occurred_at", "source", "occurred_at"),
        Index("idx_audit_occurred_at", "occurred_at"),
        Index("uk_audit_audit_id", "audit_id", unique=True)
    )

    audit_id = Column(
        String(64), nullable=False,
        comment="审计 ID，审计事件的唯一标识"
    )
    action = Column(
        String(64), nullable=False,
        comment="操作类型，格式为 resource.operation，如 model.register"
    )
    resource = Column(
        String(64), nullable=False,
        comment="资源类型，表示发起当前操作的业务模块，可选值：model / version / deployment / experiment"
    )
    operation = Column(
        String(64), nullable=False,
        comment="操作名称，如 register / create / delete / update"
    )
    target_type = Column(
        String(64), nullable=False,
        comment="目标类型，表示当前操作实际作用的业务对象类型，可选值：model / version / deployment / experiment"
    )
    target_id = Column(
        String(64), nullable=False,
        comment="目标 ID"
    )
    source = Column(
        String(16), nullable=False, server_default=text("'system'"),
        comment="来源类型，可选值：http / cli / system / worker / scheduler"
    )
    trace_id = Column(
        String(64), nullable=True,
        comment="链路追踪 ID"
    )
    request_id = Column(
        String(64), nullable=True,
        comment="请求 ID，用于关联触发当前审计事件的请求"
    )
    user = Column(
        String(64), nullable=True, server_default="system",
        comment="操作者"
    )
    ip = Column(
        String(64), nullable=True,
        comment="操作者 IP"
    )
    status = Column(
        String(16), nullable=False, server_default=text("'success'"),
        comment="操作状态，可选值：success / failed"
    )
    error = Column(
        TEXT, nullable=True,
        comment="错误信息"
    )
    before = Column(
        JSONB, nullable=True,
        comment="变更前数据，JSON 格式"
    )
    after = Column(
        JSONB, nullable=True,
        comment="变更后数据，JSON 格式"
    )
    context = Column(
        JSONB, nullable=True,
        comment="操作上下文，JSON 格式"
    )
    occurred_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="操作发生时间"
    )

    def __repr__(self):
        return (
            f"<Audit("
            f"audit_id='{self.audit_id}', "
            f"request_id='{self.request_id}', "
            f"action='{self.action}', "
            f"target_type='{self.target_type}', "
            f"target_id='{self.target_id}'"
            f")>"
        )