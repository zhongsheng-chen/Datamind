# Datamind/datamind/core/db/models/model/version.py
"""模型版本历史表定义"""

from sqlalchemy import (
    Column, String, DateTime, Text, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base
from datamind.core.domain.enums import AuditAction


class ModelVersionHistory(Base):
    """模型版本历史表"""
    __tablename__ = 'model_version_history'
    __table_args__ = (
        Index('idx_history_model_time', 'model_id', 'operation_time'),
        Index('idx_history_operator', 'operator'),
        Index('idx_history_operation', 'operation'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    operation = Column(SQLEnum(AuditAction), nullable=False)

    operator = Column(String(50), nullable=False)
    operator_ip = Column(INET, nullable=True)
    operation_time = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(Text, nullable=True)
    metadata_snapshot = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)

    # 关系
    model = relationship("ModelMetadata", back_populates="versions")

    def __repr__(self):
        return f"<ModelVersionHistory(model_id='{self.model_id}', version='{self.model_version}', operation='{self.operation}')>"