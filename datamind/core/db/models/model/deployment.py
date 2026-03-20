# Datamind/datamind/core/db/models/model/deployment.py

"""模型部署表定义
"""

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base
from datamind.core.domain.enums import DeploymentEnvironment


class ModelDeployment(Base):
    """模型部署表"""
    __tablename__ = 'model_deployments'
    __table_args__ = (
        Index('idx_deployment_active', 'is_active'),
        Index('idx_deployment_env', 'environment'),
        Index('idx_deployment_model_env', 'model_id', 'environment'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    deployment_id = Column(String(50), unique=True, nullable=False)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False)
    model_version = Column(String(20), nullable=False)

    environment = Column(SQLEnum(DeploymentEnvironment), nullable=False)
    endpoint_url = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)

    deployment_config = Column(JSONB, nullable=True)
    resources = Column(JSONB, nullable=True)

    deployed_by = Column(String(50), nullable=False)
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), nullable=True)
    health_check_details = Column(JSONB, nullable=True)

    traffic_weight = Column(Integer, default=100)
    canary_config = Column(JSONB, nullable=True)

    # 关系
    model = relationship("ModelMetadata", back_populates="deployments")

    def __repr__(self):
        return f"<ModelDeployment(deployment_id='{self.deployment_id}', model='{self.model_id}', env='{self.environment}')>"