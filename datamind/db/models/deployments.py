# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在不同环境中的部署信息，用于生成部署实例。
"""

from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表"""

    __tablename__ = "deployments"

    __table_args__ = (
        Index("idx_deployments_model_id", "model_id"),
        Index("idx_deployments_framework", "framework"),
        Index("idx_deployments_model_id_version_id", "model_id", "version_id"),
        Index("idx_deployments_model_id_environment_status", "model_id", "environment", "status"),
        Index("idx_deployments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("uk_deployments_deployment_id", "deployment_id", unique=True),
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID，部署实例的唯一标识"
    )
    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID"
    )
    version_id = Column(
        String(64),
        nullable=False,
        comment="版本 ID"
    )
    framework = Column(
        String(50),
        nullable=False,
        comment="框架类型，表示当前部署实例运行的模型框架，"
                "可选值 sklearn / xgboost / lightgbm / catboost"
    )
    environment = Column(
        String(20),
        nullable=False,
        server_default=text("'production'"),
        comment="部署环境，可选值：production / staging / development / testing"
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=text("'inactive'"),
        comment="部署状态，可选值：active / inactive"
    )
    rollout_type = Column(
        String(20),
        nullable=False,
        server_default=text("'full'"),
        comment="发布类型，仅用于标识发布方式，可选值：full / canary / shadow"
    )
    role = Column(
        String(20),
        nullable=False,
        server_default=text("'champion'"),
        comment="部署角色：champion / challenger / shadow"
    )
    effective_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效开始时间"
    )
    effective_to = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效结束时间"
    )
    config = Column(
        JSONB,
        nullable=True,
        comment="运行时配置，JSON 格式"
    )
    description = Column(
        TEXT,
        nullable=True,
        comment="部署说明"
    )
    deployed_by = Column(
        String(50),
        nullable=True,
        comment="部署人"
    )
    updated_by = Column(
        String(50),
        nullable=True,
        comment="更新人"
    )

    def __repr__(self):
        return (
            f"<Deployment("
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"environment='{self.environment}', "
            f"role='{self.role}', "
            f"status='{self.status}'"
            f")>"
        )