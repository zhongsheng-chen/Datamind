"""模型路由表.

记录部署实例的流量路由规则，
用于在请求未命中实验时选择目标部署。

核心功能：
  - Routing: 模型路由规则记录

使用示例：
  from datamind.db.models.routing import Routing

  routing = Routing(
      routing_id="rtn_0123456789abcdef",
      name="scorecard-route",
      deployment_id="dep_0123456789abcdef",
      rollout_type="canary",
      rollout_group="challenger",
      environment="production",
      enabled=True,
      traffic_ratio=0.3,
      rules={
          "match": "all",
          "conditions": [
              {
                  "field": "features.income",
                  "op": "gte",
                  "value": 1000,
              },
              {
                  "field": "features.age",
                  "op": "gte",
                  "value": 35,
              },
          ],
      },
      description="30% 灰度流量",
      created_by="admin",
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Routing(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型路由表."""

    __tablename__ = "routing"

    __table_args__ = (
        Index(
            "uk_routing_name_not_deleted",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uk_routing_deployment_id_not_deleted",
            "deployment_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_routing_rollout_type_enabled",
            "rollout_type",
            "enabled",
        ),
        Index(
            "idx_routing_rollout_group_enabled",
            "rollout_group",
            "enabled",
        ),
        Index(
            "idx_routing_environment_enabled",
            "environment",
            "enabled",
        ),
        Index(
            "idx_routing_deleted_at",
            "deleted_at",
        ),
        Index(
            "uk_routing_routing_id",
            "routing_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "rollout_type IN ("
                "'full', "
                "'canary', "
                "'shadow'"
                ")"
            ),
            name="rollout_type_valid",
        ),
        CheckConstraint(
            (
                "rollout_group IS NULL "
                "OR rollout_group IN ("
                "'champion', "
                "'challenger', "
                "'shadow'"
                ")"
            ),
            name="rollout_group_valid",
        ),
        CheckConstraint(
            (
                "environment IN ("
                "'production', "
                "'staging', "
                "'development', "
                "'testing'"
                ")"
            ),
            name="environment_valid",
        ),
        CheckConstraint(
            "traffic_ratio >= 0 AND traffic_ratio <= 1",
            name="traffic_ratio_range",
        ),
        CheckConstraint(
            (
                "rules IS NULL "
                "OR jsonb_typeof(rules) = 'object'"
            ),
            name="rules_object",
        ),
        CheckConstraint(
            (
                "effective_to IS NULL "
                "OR effective_from IS NULL "
                "OR effective_to > effective_from"
            ),
            name="effective_time_valid",
        ),
    )

    routing_id = Column(
        String(64),
        nullable=False,
        comment="路由 ID，路由规则的唯一标识",
    )

    name = Column(
        String(128),
        nullable=False,
        comment="路由名称",
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID",
    )

    rollout_type = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'full'"
        ),
        comment=(
            "发布类型，可选值："
            "full / canary / shadow"
        ),
    )

    rollout_group = Column(
        String(64),
        nullable=True,
        comment=(
            "发布分组，可选值："
            "champion / challenger / shadow"
        ),
    )

    environment = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'production'"
        ),
        comment=(
            "路由环境，可选值："
            "production / staging / development / testing"
        ),
    )

    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否启用",
    )

    traffic_ratio = Column(
        Float,
        nullable=False,
        server_default=text(
            "0"
        ),
        comment="流量占比，取值范围 0.0～1.0",
    )

    rules = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "路由规则，JSON 格式。"
            "可记录匹配模式、条件列表和路由元信息等"
        ),
    )

    rules_metadata = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "规则元信息，JSON 格式。"
            "可记录文件名、文件大小和上传时间等"
        ),
    )

    effective_from = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="生效时间",
    )

    effective_to = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="失效时间",
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="路由说明",
    )

    created_by = Column(
        String(50),
        nullable=True,
        comment="创建人",
    )

    updated_by = Column(
        String(50),
        nullable=True,
        comment="更新人",
    )

    deleted_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="逻辑删除时间",
    )

    deleted_by = Column(
        String(50),
        nullable=True,
        comment="逻辑删除操作人",
    )

    deletion_reason = Column(
        TEXT,
        nullable=True,
        comment="逻辑删除原因",
    )

    def __repr__(
            self,
    ) -> str:
        """返回模型路由字符串表示."""
        return (
            f"<Routing("
            f"routing_id='{self.routing_id}', "
            f"name='{self.name}', "
            f"deployment_id='{self.deployment_id}', "
            f"environment='{self.environment}', "
            f"rollout_type='{self.rollout_type}', "
            f"rollout_group='{self.rollout_group}', "
            f"traffic_ratio={self.traffic_ratio}, "
            f"enabled={self.enabled}"
            f")>"
        )
