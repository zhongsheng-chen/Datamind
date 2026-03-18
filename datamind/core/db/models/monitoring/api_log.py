# Datamind/datamind/core/db/models/monitoring/api_log.py

"""API调用日志表定义"""

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, BigInteger,
    Numeric, Index,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func

from datamind.core.db.base import Base
from datamind.core.domain.enums import TaskType


class ApiCallLog(Base):
    """API调用日志表"""
    __tablename__ = 'api_call_logs'
    __table_args__ = (
        Index('idx_api_time', 'created_at'),
        Index('idx_api_app_model', 'application_id', 'model_id'),
        Index('idx_api_request_id', 'request_id'),
        Index('idx_api_status', 'status_code'),
        Index('idx_api_task_type', 'task_type'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(50), unique=True, nullable=False)
    application_id = Column(String(50), nullable=False, index=True)
    model_id = Column(String(50), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)

    endpoint = Column(String(100), nullable=False)

    request_data = Column(JSONB, nullable=True)
    response_data = Column(JSONB, nullable=True)
    request_headers = Column(JSONB, nullable=True)
    response_headers = Column(JSONB, nullable=True)

    processing_time_ms = Column(Integer, nullable=False)
    model_inference_time_ms = Column(Integer, nullable=True)
    total_time_ms = Column(Integer, nullable=True)

    status_code = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(200), nullable=True)
    api_key = Column(String(100), nullable=True)
    user_id = Column(String(50), nullable=True)

    cost_credits = Column(Numeric(10, 4), nullable=True)
    billing_info = Column(JSONB, nullable=True)

    business_metrics = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    partition_date = Column(DateTime, nullable=False,
                          server_default=func.date_trunc('day', func.now()))

    def __repr__(self):
        return f"<ApiCallLog(request_id='{self.request_id}', model='{self.model_id}', status={self.status_code})>"