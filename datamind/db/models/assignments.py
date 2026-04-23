# datamind/db/models/assignments.py

"""请求分配表

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """请求分配记录表

    属性：
        request_id: 请求唯一标识
        user_id: 用户标识（可选，用于用户级追踪）
        model_id: 被分配到的模型ID
        version: 被分配到的模型版本
        source: 分配来源（routing/experiment/deployment）
        strategy: 分配策略（random/hash/weighted）
        context: 分配上下文（实验ID、分组、权重等）
        routed_at: 路由分配时间
    """

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_model_id", "model_id"),
        Index("idx_assignments_request_id", "request_id"),
        Index("idx_assignments_user_id", "user_id"),
        Index("idx_assignments_model_version", "model_id", "version"),
        Index("idx_assignments_created_at", "created_at"),
        Index("idx_assignments_source", "source"),
    )

    request_id = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=True)

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)

    source = Column(String(20), nullable=False)

    strategy = Column(String(20), nullable=True)

    context = Column(JSON, nullable=True)

    routed_at = Column(DateTime, nullable=False)


    def __repr__(self):
        return (
            f"<Assignment("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )