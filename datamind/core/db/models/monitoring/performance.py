# Datamind/datamind/core/db/models/monitoring/performance.py
"""模型性能监控表定义"""

from sqlalchemy import (
    Column, String, Integer, DateTime, Float, BigInteger,
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base
from datamind.core.domain.enums import TaskType


class ModelPerformanceMetrics(Base):
    """模型性能监控表"""
    __tablename__ = 'model_performance_metrics'
    __table_args__ = (
        Index('idx_performance_model_date', 'model_id', 'date'),
        Index('idx_performance_task_type', 'task_type'),
        UniqueConstraint('model_id', 'model_version', 'date', name='uq_model_metric_date'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)

    date = Column(DateTime, nullable=False)

    total_requests = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    timeout_count = Column(Integer, default=0)

    avg_response_time_ms = Column(Float)
    p50_response_time_ms = Column(Float)
    p95_response_time_ms = Column(Float)
    p99_response_time_ms = Column(Float)
    max_response_time_ms = Column(Integer)
    min_response_time_ms = Column(Integer)

    # 评分卡专用指标
    avg_score = Column(Float, nullable=True)
    score_distribution = Column(JSONB, nullable=True)
    score_bins = Column(JSONB, nullable=True)

    # 反欺诈专用指标
    fraud_rate = Column(Float, nullable=True)
    fraud_count = Column(Integer, nullable=True)
    risk_distribution = Column(JSONB, nullable=True)
    risk_levels = Column(JSONB, nullable=True)

    feature_importance_drift = Column(JSONB, nullable=True)

    avg_cpu_usage = Column(Float, nullable=True)
    avg_memory_usage = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    model = relationship("ModelMetadata", back_populates="performance_records")

    def __repr__(self):
        return f"<ModelPerformanceMetrics(model='{self.model_id}', date='{self.date}')>"