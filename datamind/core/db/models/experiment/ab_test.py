# Datamind/datamind/core/db/models/experiment/ab_test.py
"""A/B测试配置表定义"""

from sqlalchemy import (
    Column, String, DateTime, Text, Float, BigInteger,
    Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base
from datamind.core.domain.enums import TaskType, ABTestStatus


class ABTestConfig(Base):
    """A/B测试配置表"""
    __tablename__ = 'ab_test_configs'
    __table_args__ = (
        Index('idx_abtest_status', 'status'),
        Index('idx_abtest_dates', 'start_date', 'end_date'),
        Index('idx_abtest_task_type', 'task_type'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), unique=True, nullable=False)
    test_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    task_type = Column(SQLEnum(TaskType), nullable=False)

    groups = Column(JSONB, nullable=False)

    traffic_allocation = Column(Float, default=100.0)
    assignment_strategy = Column(String(20), default='random')

    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)

    status = Column(SQLEnum(ABTestStatus), default=ABTestStatus.DRAFT)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    metrics = Column(JSONB, nullable=True)
    winning_criteria = Column(JSONB, nullable=True)

    results = Column(JSONB, nullable=True)
    winning_group = Column(String(50), nullable=True)

    # 关系
    assignments = relationship("ABTestAssignment", back_populates="test")

    def __repr__(self):
        return f"<ABTestConfig(test_id='{self.test_id}', name='{self.test_name}', status='{self.status}')>"