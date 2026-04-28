# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在生产环境中的生效区间与流量分配。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Float, Index, DateTime

from datamind.db.core import Base, IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表

    属性：
        model_id: 所属模型 ID
        version: 部署的版本号
        framework: 模型框架，可选值 sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow
        status: 部署状态，可选值：active / inactive
        traffic_ratio: 流量占比，取值范围 0.0 ~ 1.0
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        deployed_by: 部署操作人
        description: 部署说明
    """

    __tablename__ = "deployments"

    __table_args__ = (
        Index("idx_deployments_model_id", "model_id"),
        Index("idx_deployments_version", "model_id", "version"),
        Index("idx_deployments_framework", "framework"),
        Index("idx_deployments_status", "status"),
        Index("idx_deployments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("uk_deployments_model_id_version", "model_id", "version", unique=True),
        CheckConstraint("traffic_ratio >= 0 AND traffic_ratio <= 1", name="ck_traffic_ratio_range"),
    )

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False, default="active")
    traffic_ratio = Column(Float, nullable=False, default=1.0)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    deployed_by = Column(String(50))
    description = Column(String(255))

    def __repr__(self):
        return f"<Deployment(model_id='{self.model_id}', version='{self.version}', status='{self.status}')>"