"""实验分组表

记录实验下的分组配置，用于定义对照组、实验组、
对应部署和实验内流量权重。

核心功能：
  - Variant: 实验分组记录

使用示例：
  from datamind.db.models.variants import Variant

  variant = Variant(
      variant_id="var_0123456789abcdef",
      experiment_id="exp_0123456789abcdef",
      name="control",
      deployment_id="dep_0123456789abcdef",
      weight=0.5,
      is_control=True,
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


class Variant(
    IdMixin,
    TimestampMixin,
    Base,
):
    """实验分组表"""

    __tablename__ = "variants"

    __table_args__ = (
        Index(
            "idx_variants_experiment_id",
            "experiment_id",
        ),
        Index(
            "idx_variants_deployment_id",
            "deployment_id",
        ),
        Index(
            "idx_variants_status",
            "status",
        ),
        Index(
            "idx_variants_created_at",
            "created_at",
        ),
        Index(
            "idx_variants_deleted_at",
            "deleted_at",
        ),
        Index(
            "idx_variants_experiment_status",
            "experiment_id",
            "status",
        ),
        Index(
            "uk_variants_variant_id",
            "variant_id",
            unique=True,
        ),
        Index(
            "uk_variants_experiment_name",
            "experiment_id",
            "name",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL"
            ),
        ),
        Index(
            "uk_variants_experiment_deployment",
            "experiment_id",
            "deployment_id",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL"
            ),
        ),
        Index(
            "uk_variants_active_control",
            "experiment_id",
            unique=True,
            postgresql_where=text(
                "is_control = true "
                "AND status = 'active' "
                "AND deleted_at IS NULL"
            ),
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="weight_range",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'inactive', "
                "'archived'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "config IS NULL "
                "OR jsonb_typeof(config) = 'object'"
            ),
            name="config_object",
        ),
    )

    variant_id = Column(
        String(64),
        nullable=False,
        comment="实验分组 ID，实验分组的唯一标识",
    )

    experiment_id = Column(
        String(64),
        nullable=False,
        comment="实验 ID",
    )

    name = Column(
        String(64),
        nullable=False,
        comment=(
            "实验分组名称，例如 "
            "control / treatment"
        ),
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="实验分组对应的部署 ID",
    )

    weight = Column(
        Float,
        nullable=False,
        server_default=text(
            "0"
        ),
        comment="实验内分组权重，取值范围 0.0～1.0",
    )

    is_control = Column(
        Boolean,
        nullable=False,
        server_default=text(
            "false"
        ),
        comment="是否为对照组",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment=(
            "实验分组状态，可选值："
            "active / inactive / archived"
        ),
    )

    config = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "实验分组配置，JSON 对象，"
            "用于保存分组参数和策略说明"
        ),
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="实验分组说明",
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

    deletion_id = Column(
        String(64),
        nullable=True,
        comment="逻辑删除批次 ID",
    )

    deletion_reason = Column(
        TEXT,
        nullable=True,
        comment="逻辑删除原因",
    )

    def __repr__(
            self,
    ) -> str:
        """返回实验分组字符串表示"""
        return (
            f"<Variant("
            f"variant_id='{self.variant_id}', "
            f"experiment_id='{self.experiment_id}', "
            f"name='{self.name}', "
            f"deployment_id='{self.deployment_id}', "
            f"weight={self.weight}, "
            f"is_control={self.is_control}, "
            f"status='{self.status}'"
            f")>"
        )
