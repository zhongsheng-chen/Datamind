# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在不同环境中的部署信息，用于生成部署实例。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Text, Float, DateTime, Index, text

from datamind.db.core import Base, IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表"""

    __tablename__ = "deployments"

    __table_args__ = (
        Index("idx_deployments_model_id", "model_id"),
        Index("idx_deployments_framework", "framework"),
        Index("idx_deployments_model_version", "model_id", "version_id"),
        Index("idx_deployments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("idx_deployments_environment_variant_status", "environment", "variant", "status"),
        Index("uk_deployments_deployment_id", "deployment_id", unique=True),
        CheckConstraint("traffic_ratio >= 0 AND traffic_ratio <= 1", name="ck_traffic_ratio_range"),
    )

    deployment_id = Column(
        String(64), nullable=False,
        comment="部署 ID，部署实例的唯一标识"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="模型 ID"
    )
    version_id = Column(
        String(64), nullable=False,
        comment="版本 ID"
    )
    framework = Column(
        String(50), nullable=False,
        comment="框架类型，表示当前部署实例运行的模型框架，"
                "可选值 sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow"
    )
    status = Column(
        String(20), nullable=False, server_default=text("'active'"),
        comment="部署状态，可选值：active / inactive"
    )
    environment = Column(
        String(20), nullable=False, server_default=text("'production'"),
        comment="部署环境，可选值：production / staging / development / testing"
    )
    rollout_type = Column(
        String(20), nullable=False, server_default=text("'full'"),
        comment="发布类型，仅用于标识发布方式，可选值：full / canary / shadow"
    )
    variant = Column(
        String(20), nullable=False, server_default=text("'primary'"),
        comment="部署角色：primary / canary"
    )
    traffic_ratio = Column(
        Float, nullable=False, server_default=text("1.0"),
        comment="流量占比，取值范围 0.0 ~ 1.0"
    )
    effective_from = Column(
        DateTime(timezone=True), nullable=True,
        comment="生效开始时间"
    )
    effective_to = Column(
        DateTime(timezone=True), nullable=True,
        comment="生效结束时间"
    )
    deployed_by = Column(
        String(50), nullable=True,
        comment="部署人"
    )
    updated_by = Column(
        String(50), nullable=True,
        comment="更新人"
    )
    description = Column(
        Text, nullable=True,
        comment="部署说明"
    )

    def __repr__(self):
        return (
            f"<Deployment("
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"environment='{self.environment}', "
            f"variant='{self.variant}', "
            f"status='{self.status}'"
            f")>"
        )