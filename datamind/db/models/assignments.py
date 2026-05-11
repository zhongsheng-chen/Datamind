# datamind/db/models/assignments.py

"""请求分配表

记录每个请求分配到的模型版本及决策过程，用于 A/B 测试与灰度发布的执行结果记录。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """请求分配记录表"""

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_model_id", "model_id"),
        Index("idx_assignments_version_id", "version_id"),
        Index("idx_assignments_deployment_id", "deployment_id"),
        Index("idx_assignments_experiment_id", "experiment_id"),
        Index("idx_assignments_customer_id", "customer_id"),
        Index("idx_assignments_created_at", "created_at"),
        Index("idx_assignments_source", "source"),
        Index("uk_assignments_assignment_id", "assignment_id", unique=True),
        Index("uk_assignments_request_id", "request_id", unique=True)
    )

    assignment_id = Column(
        String(64), nullable=False,
        comment="分配 ID，分配的唯一标识"
    )
    request_id = Column(
        String(64), nullable=False,
        comment="请求 ID"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="被分配到的模型 ID"
    )
    version_id = Column(
        String(50), nullable=False,
        comment="被分配的版本 ID"
    )
    deployment_id = Column(
        String(64), nullable=True,
        comment="命中的部署 ID"
    )
    experiment_id = Column(
        String(64), nullable=True,
        comment="命中的实验 ID"
    )
    customer_id = Column(
        String(64), nullable=False,
        comment="请求主体标识"
    )
    source = Column(
        String(20), nullable=False,
        comment="路由来源，可选值：experiment / deployment / routing"
    )
    strategy = Column(
        String(20), nullable=True,
        comment="流量分配策略，可选值：random / consistent / bucket / weighted"
    )
    bucket = Column(
        String(32), nullable=True,
        comment="分桶标识"
    )
    group = Column(
        String(32), nullable=True,
        comment="实验分组，如 control / treatment"
    )
    weight = Column(
        Float,
        nullable=True,
        comment="分配权重，表示当前请求在该实验分组中的概率权重"
    )
    context = Column(
        JSONB, nullable=True,
        comment="分配上下文，JSON 格式。包含所有分配过程的信息，仅用于跟踪和调试"
    )
    routed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="路由分配时间，表示请求被分配到目标模型版本的实际时间"
    )

    def __repr__(self):
        return (
            f"<Assignment("
            f"assignment_id='{self.assignment_id}', "
            f"request_id='{self.request_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )