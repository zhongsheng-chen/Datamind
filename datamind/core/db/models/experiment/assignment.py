# Datamind/datamind/core/db/models/experiment/assignment.py

"""A/B测试分配记录表定义
"""

from sqlalchemy import (
    Column, String, DateTime, BigInteger,
    ForeignKey, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base


class ABTestAssignment(Base):
    """A/B测试分配记录表"""
    __tablename__ = 'ab_test_assignments'
    __table_args__ = (
        Index('idx_ab_assign_test_user', 'test_id', 'user_id'),
        Index('idx_ab_assign_time', 'assigned_at'),
        Index('idx_ab_assign_model', 'model_id'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), ForeignKey('public.ab_test_configs.test_id', ondelete='CASCADE'),
                    nullable=False)
    user_id = Column(String(50), nullable=False)
    group_name = Column(String(50), nullable=False)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assignment_hash = Column(String(64), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    test = relationship("ABTestConfig", back_populates="assignments")
    model = relationship("ModelMetadata", back_populates="ab_test_assignments")

    def __repr__(self):
        return f"<ABTestAssignment(test='{self.test_id}', user='{self.user_id}', group='{self.group_name}')>"