# datamind/db/models/routing.py

"""模型路由表

定义模型版本的默认路由规则，当请求未命中实验或灰度发布时使用该规则分配模型版本。
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
        Index("idx_routing_routing_id", "routing_id", unique=True)
    )

    routing_id = Column(
        String(64), nullable=False,
        comment="路由 ID，路由的唯一标志"
    )
    name = Column(
        String(100), nullable=True,
        comment="路由名称"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="模型 ID"
    )
    strategy = Column(
        String(20), nullable=False,
        comment="版本选择策略，可选值：random / consistent / bucket / weighted"
    )
    config = Column(
        JSONB, nullable=True,
        comment="策略配置参数，JSON 格式"
    )
    enabled = Column(
        Boolean, nullable=False, server_default=text("true"),
        comment="是否启用"
    )

    def __repr__(self):
        return (
            f"<Routing("
            f"routing_id='{self.routing_id}', "
            f"model_id='{self.model_id}', "
            f"enabled='{self.enabled}'"
            f")>"
        )