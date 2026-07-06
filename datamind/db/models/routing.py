# datamind/db/models/routing.py

"""模型路由表

定义模型版本的默认路由规则，当请求未命中实验或灰度发布时使用该规则分配模型版本。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Float, Boolean, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Routing(Base, IdMixin, TimestampMixin):
    """模型路由表"""

    __tablename__ = "routing"

    __table_args__ = (
        Index(
            "idx_routing_deployment_id",
            "deployment_id"
        ),
        Index(
            "idx_routing_rollout_type_enabled",
            "rollout_type",
            "enabled"
        ),
        Index(
            "idx_routing_rollout_group_enabled",
            "rollout_group",
            "enabled"
        ),
        Index(
            "idx_routing_environment_enabled",
            "environment",
            "enabled"
        ),
        Index(
            "uk_routing_routing_id",
            "routing_id",
            unique=True
        ),
        CheckConstraint(
            "traffic_ratio >= 0 AND traffic_ratio <= 1",
            name="ck_traffic_ratio_range"
        ),
    )

    routing_id = Column(
        String(64),
        nullable=False,
        comment="路由 ID，路由的唯一标志"
    )
    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID"
    )
    rollout_type = Column(
        String(20),
        nullable=False,
        server_default=text("'full'"),
        comment="发布类型，仅用于标识发布方式，可选值：full / canary / shadow"
    )
    rollout_group = Column(
        String(64),
        nullable=True,
        comment="发布分组"
    )
    environment = Column(
        String(20),
        nullable=False,
        server_default=text("'production'"),
        comment="路由环境"
    )
    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="是否启用"
    )
    traffic_ratio = Column(
        Float,
        nullable=False,
        server_default=text("0"),
        comment="流量占比，取值范围 0.0 ~ 1.0"
    )
    rules = Column(
        JSONB,
        nullable=True,
        comment="路由规则配置，JSON 格式"
    )
    description = Column(
        TEXT,
        nullable=True,
        comment="路由说明"
    )
    created_by = Column(
        String(50),
        nullable=True,
        comment="创建人"
    )
    updated_by = Column(
        String(50),
        nullable=True,
        comment="更新人"
    )

    def __repr__(self):
        return (
            f"<Routing("
            f"routing_id='{self.routing_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"environment='{self.environment}', "
            f"enabled='{self.enabled}'"
            f")>"
        )
