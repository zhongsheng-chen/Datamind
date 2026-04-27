# datamind/db/models/audit.py

"""审计日志表

记录系统控制平面的所有变更行为，满足金融级审计要求。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表

    属性：
        user: 操作者
        ip: 操作者IP地址
        action: 操作类型（create/update/delete/deploy/pause/resume/rollback）
        target_type: 目标类型（experiment/deployment/routing/model/version）
        target_id: 目标ID
        before: 变更前数据
        after: 变更后数据
        context: 操作上下文（原因、审批信息等）
        occurred_at: 实际操作发生时间
    """

    __tablename__ = "audit"

    __table_args__ = (
        Index("idx_audit_action", "action"),
        Index("idx_audit_user", "user"),
        Index("idx_audit_target", "target_type", "target_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
        Index("idx_audit_target_occurred_at", "target_type", "occurred_at"),
        Index("idx_audit_created_at", "created_at"),
    )

    user = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)

    action = Column(String(50), nullable=False)

    target_type = Column(String(50), nullable=False)
    target_id = Column(String(64), nullable=False)

    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)

    context = Column(JSON, nullable=True)

    occurred_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Audit(action='{self.action}', target='{self.target_type}', user='{self.user}, ip='{self.ip}')>"