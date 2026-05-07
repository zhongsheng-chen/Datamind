# datamind/db/models/routing.py

"""模型路由表

定义模型版本的流量分配规则，支持多种路由策略。
"""

from sqlalchemy import Column, String, Boolean, Index, text
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Routing(Base, IdMixin, TimestampMixin):
    """模型路由表"""

    __tablename__ = "routing"

    __table_args__ = (
        Index("idx_routing_model_id", "model_id"),
        Index("idx_routing_strategy", "strategy"),
        Index("idx_routing_enabled", "enabled"),
    )

    model_id = Column(
        String(64), nullable=False,
        comment="所属模型 ID"
    )
    strategy = Column(
        String(20), nullable=False,
        comment="路由策略，可选值：random / consistent / bucket / round_robin / weighted"
    )
    config = Column(
        JSONB, nullable=True,
        comment="策略配置，JSON 格式，如权重、桶范围等"
    )
    enabled = Column(
        Boolean, nullable=False, server_default=text("true"),
        comment="是否启用"
    )

    def __repr__(self):
        return (
            f"<Routing("
            f"model_id='{self.model_id}', "
            f"strategy='{self.strategy}', "
            f"enabled='{self.enabled}'"
            f")>"
        )