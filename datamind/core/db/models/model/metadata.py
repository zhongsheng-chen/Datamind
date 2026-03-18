# Datamind/datamind/core/db/models/model/metadata.py
"""模型元数据表定义"""

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text,
    BigInteger, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base
from datamind.core.domain.enums import (
    TaskType, ModelType, Framework, ModelStatus
)


class ModelMetadata(Base):
    """模型元数据表"""
    __tablename__ = 'model_metadata'
    __table_args__ = (
        Index('idx_model_status', 'status', 'is_production'),
        Index('idx_model_abtest', 'ab_test_group', 'status'),
        Index('idx_model_name_version', 'model_name', 'model_version', unique=True),
        Index('idx_model_created_at', 'created_at'),
        Index('idx_model_task_type', 'task_type'),
        Index('idx_model_type_framework', 'model_type', 'framework'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)
    model_type = Column(SQLEnum(ModelType), nullable=False)
    framework = Column(SQLEnum(Framework), nullable=False)

    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(BigInteger, nullable=False)

    input_features = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=False)

    model_params = Column(JSONB, nullable=True)
    feature_importance = Column(JSONB, nullable=True)
    performance_metrics = Column(JSONB, nullable=True)

    status = Column(SQLEnum(ModelStatus), default=ModelStatus.INACTIVE)
    is_production = Column(Boolean, default=False)
    ab_test_group = Column(String(50), nullable=True)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)

    tags = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    # 关系
    versions = relationship("ModelVersionHistory", back_populates="model", cascade="all, delete-orphan")
    deployments = relationship("ModelDeployment", back_populates="model", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="model")
    performance_records = relationship("ModelPerformanceMetrics", back_populates="model")
    ab_test_assignments = relationship("ABTestAssignment", back_populates="model")

    def __repr__(self):
        return f"<ModelMetadata(model_id='{self.model_id}', name='{self.model_name}', version='{self.model_version}')>"