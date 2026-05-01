# datamind/db/models/audit.py

"""审计日志表

记录系统控制平面的所有变更行为，提供变更追溯和审计能力。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表

    属性：
        action: 操作类型，格式为 resource.operation，如 model.register
        resource: 资源类型，可选值：model / deployment / experiment
        operation: 操作名称，如 register / create / delete / update
        target_type: 目标类型，可选值：model / version / deployment / experiment
        target_id: 目标 ID
        source: 来源类型，可选值：http / system / worker / cron
        trace_id: 链路追踪 ID
        request_id: 请求 ID
        user: 操作者
        ip: 操作者 IP 地址（HTTP 请求时记录，system/worker 时为 None）
        status: 操作状态，可选值：success / failed
        error: 错误信息
        before: 变更前数据，JSON 格式
        after: 变更后数据，JSON 格式
        context: 操作上下文，JSON 格式
        occurred_at: 操作发生时间
    """

    __tablename__ = "audit"

    __table_args__ = (
        Index("idx_audit_target_id_occurred_at", "target_type", "target_id", "occurred_at"),
        Index("idx_audit_trace_id_occurred_at", "trace_id", "occurred_at", postgresql_where=text("trace_id IS NOT NULL")),
        Index("idx_audit_user_occurred_at", "user", "occurred_at"),
        Index("idx_audit_target_type_occurred_at", "target_type", "occurred_at"),
        Index("idx_audit_failed_occurred_at", "occurred_at", postgresql_where=text("status = 'failed'")),
        Index("idx_audit_source_occurred_at", "source", "occurred_at"),
        Index("idx_audit_occurred_at", "occurred_at"),
    )

    action = Column(String(64), nullable=False)
    resource = Column(String(64), nullable=False)
    operation = Column(String(64), nullable=False)

    target_type = Column(String(64), nullable=False)
    target_id = Column(String(64), nullable=False)

    source = Column(String(16), nullable=False, server_default=text("'system'"))

    trace_id = Column(String(64), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)

    user = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)

    status = Column(String(16), nullable=False, server_default=text("'success'"))
    error = Column(TEXT, nullable=True)

    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    context = Column(JSONB, nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<Audit(action='{self.action}', target_type='{self.target_type}', target_id='{self.target_id}', source='{self.source}')>"