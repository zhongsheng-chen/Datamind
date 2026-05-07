# datamind/db/models/assignments.py

"""请求分配表

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的流量追踪。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """请求分配记录表"""

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_model_id", "model_id"),
        Index("idx_assignments_request_id", "request_id"),
        Index("idx_assignments_model_version", "model_id", "version"),
        Index("idx_assignments_created_at", "created_at"),
        Index("idx_assignments_source", "source"),
        Index("idx_assignments_user", "user"),
    )

    request_id = Column(
        String(64), nullable=False,
        comment="请求唯一标识"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="被分配到的模型 ID"
    )
    version = Column(
        String(50), nullable=False,
        comment="被分配到的模型版本"
    )
    user = Column(
        String(64), nullable=True,
        comment="用户标识，用于用户级追踪"
    )
    source = Column(
        String(20), nullable=False,
        comment="分配来源，可选值：routing / experiment / deployment"
    )
    strategy = Column(
        String(20), nullable=True,
        comment="分配策略，可选值：random / hash / weighted"
    )
    context = Column(
        JSONB, nullable=True,
        comment="分配上下文，如实验 ID、分组、权重等"
    )
    routed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="路由分配时间"
    )

    def __repr__(self):
        return (
            f"<Assignment("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )