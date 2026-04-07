# datamind/core/db/models/audit/audit_log.py

"""审计日志表定义
"""

from sqlalchemy import (
    Column, String, DateTime, Text, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import AuditAction


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = 'audit_logs'
    __table_args__ = (
        Index('idx_audit_time', 'created_at'),
        Index('idx_audit_operator', 'operator'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_event', 'event_type'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_model', 'model_id'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    audit_id = Column(String(50), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)

    action = Column(
        SQLEnum(
            AuditAction,
            name="audit_action_enum",
            values_callable=enum_values
        ),
        nullable=False
    )

    operator = Column(String(50), nullable=False)
    operator_ip = Column(INET, nullable=True)
    operator_role = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True)

    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(50), nullable=True)
    resource_name = Column(String(100), nullable=True)

    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    changes = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)

    result = Column(String(20), nullable=True)  # success, failure, pending
    reason = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='SET NULL'),
                      nullable=True)

    # 关系
    model = relationship("ModelMetadata", back_populates="audit_logs")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AuditLog(audit_id='{self.audit_id}', action='{self.action}', operator='{self.operator}')>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'audit_id': self.audit_id,
            'event_type': self.event_type,
            'action': self.action.value if self.action else None,
            'operator': self.operator,
            'operator_ip': str(self.operator_ip) if self.operator_ip else None,
            'operator_role': self.operator_role,
            'session_id': self.session_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'before_state': self.before_state,
            'after_state': self.after_state,
            'changes': self.changes,
            'details': self.details,
            'result': self.result,
            'reason': self.reason,
            'error_code': self.error_code,
            'model_id': self.model_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }