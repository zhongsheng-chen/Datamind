# datamind/db/models/variants.py

"""实验分组表

记录实验下的不同分组配置，
用于定义对照组、实验组及其对应的部署和流量权重。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Float, Boolean, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Variant(Base, IdMixin, TimestampMixin):
    """实验分组表"""

    __tablename__ = "variants"

    __table_args__ = (
        Index("idx_variants_experiment_id", "experiment_id"),
        Index("idx_variants_deployment_id", "deployment_id"),
        Index("idx_variants_status", "status"),
        Index("idx_variants_created_at", "created_at"),
        Index("idx_variants_experiment_status", "experiment_id", "status"),
        Index("uk_variants_variant_id", "variant_id", unique=True),
        Index("uk_variants_experiment_name", "experiment_id", "name", unique=True),
        CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="ck_weight_range"
        ),
    )

    variant_id = Column(
        String(64),
        nullable=False,
        comment="实验分组 ID，实验分组的唯一标识"
    )
    experiment_id = Column(
        String(64),
        nullable=False,
        comment="实验 ID"
    )
    name = Column(
        String(64),
        nullable=False,
        comment="实验分组名称，例如 control / treatment / challenger"
    )
    deployment_id = Column(
        String(64),
        nullable=False,
        comment="实验分组对应的部署 ID"
    )
    weight = Column(
        Float,
        nullable=False,
        server_default=text("0"),
        comment="实验内分组权重，取值范围 0.0 ~ 1.0"
    )
    is_control = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否为对照组"
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        comment="实验分组状态，可选值：active / inactive / archived"
    )
    config = Column(
        JSONB,
        nullable=True,
        comment="实验分组配置，JSON 格式。可保存分组参数、策略说明等信息"
    )
    description = Column(
        TEXT,
        nullable=True,
        comment="实验分组说明"
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
            f"<Variant("
            f"variant_id='{self.variant_id}', "
            f"experiment_id='{self.experiment_id}', "
            f"name='{self.name}', "
            f"deployment_id='{self.deployment_id}', "
            f"weight='{self.weight}'"
            f")>"
        )