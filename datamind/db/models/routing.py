# datamind/db/models/routing.py

"""模型路由表

定义模型版本的流量分配规则，支持多种路由策略。
"""

from sqlalchemy import Column, String, Boolean, JSON, Index

from datamind.db.core import Base, IdMixin, TimestampMixin


class Routing(Base, IdMixin, TimestampMixin):
    """模型路由表

    属性：
        model_id: 所属模型ID
        strategy: 路由策略（RANDOM/CONSISTENT/BUCKET/ROUND_ROBIN/WEIGHTED）
        config: 策略配置（权重、桶范围等）
        enabled: 是否启用（true/false）
    """

    __tablename__ = "routing"

    __table_args__ = (
        Index("idx_routing_model_id", "model_id"),
        Index("idx_routing_strategy", "strategy"),
        Index("idx_routing_enabled", "enabled"),
    )

    model_id = Column(String(64), nullable=False)

    strategy = Column(String(20), nullable=False)

    config = Column(JSON, nullable=True)

    enabled = Column(Boolean, nullable=False, default="true")

    def __repr__(self):
        return f"<Routing(model_id='{self.model_id}', strategy='{self.strategy}', enabled='{self.enabled}')>"