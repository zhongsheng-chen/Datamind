"""请求决策表.

记录请求的最终路由结果和业务决策，
用于追踪模型版本、部署及实验分组的选择过程。

核心功能：
  - Decision: 请求决策记录

使用示例：
  from datamind.db.models.decisions import Decision

  decision = Decision(
      decision_id="dcs_0123456789abcdef",
      request_id="req_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      deployment_id="dep_0123456789abcdef",
      experiment_id="exp_0123456789abcdef",
      variant_id="var_0123456789abcdef",
      assignment_id="asn_0123456789abcdef",
      subject_key="customer_10001",
      subject_type="customer",
      source="experiment",
      strategy="hash",
      bucket="bucket_0089",
      group="treatment",
      weight=0.5,
      decision="approve",
      context={
          "worker_id": "worker-1",
          "environment": "production",
          ...
      },
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Decision(
    IdMixin,
    TimestampMixin,
    Base,
):
    """请求决策记录表."""

    __tablename__ = "decisions"

    __table_args__ = (
        Index(
            "idx_decisions_request_latest",
            "request_id",
            text("decided_at DESC"),
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "idx_decisions_model_id",
            "model_id",
        ),
        Index(
            "idx_decisions_version_id",
            "version_id",
        ),
        Index(
            "idx_decisions_deployment_id",
            "deployment_id",
        ),
        Index(
            "idx_decisions_experiment_id",
            "experiment_id",
        ),
        Index(
            "idx_decisions_variant_id",
            "variant_id",
        ),
        Index(
            "idx_decisions_assignment_id",
            "assignment_id",
        ),
        Index(
            "idx_decisions_subject_key",
            "subject_key",
        ),
        Index(
            "idx_decisions_created_at",
            "created_at",
        ),
        Index(
            "idx_decisions_source",
            "source",
        ),
        Index(
            "uk_decisions_decision_id",
            "decision_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "source IN ("
                "'experiment', "
                "'routing', "
                "'deployment', "
                "'shadow', "
                "'manual'"
                ")"
            ),
            name="source_valid",
        ),
        CheckConstraint(
            (
                "strategy IS NULL "
                "OR strategy IN ("
                "'manual', "
                "'hash', "
                "'weighted', "
                "'fallback'"
                ")"
            ),
            name="strategy_valid",
        ),
        CheckConstraint(
            (
                "weight IS NULL "
                "OR (weight >= 0 AND weight <= 1)"
            ),
            name="weight_range",
        ),
        CheckConstraint(
            (
                "context IS NULL "
                "OR jsonb_typeof(context) = 'object'"
            ),
            name="context_object",
        ),
    )

    decision_id = Column(
        String(64),
        nullable=False,
        comment="决策 ID，决策记录的唯一标识",
    )

    request_id = Column(
        String(64),
        nullable=False,
        comment="请求 ID",
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="命中的模型 ID",
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="命中的版本 ID",
    )

    deployment_id = Column(
        String(64),
        nullable=True,
        comment="命中的部署 ID",
    )

    experiment_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验 ID",
    )

    variant_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验分组 ID",
    )

    assignment_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验分配 ID",
    )

    subject_key = Column(
        String(128),
        nullable=True,
        comment="请求主体标识，例如客户号、订单号、申请单号",
    )

    subject_type = Column(
        String(32),
        nullable=True,
        comment=(
            "请求主体类型，例如 "
            "customer / order / application"
        ),
    )

    source = Column(
        String(20),
        nullable=False,
        comment=(
            "决策来源，可选值："
            "experiment / routing / deployment / shadow / manual"
        ),
    )

    strategy = Column(
        String(20),
        nullable=True,
        comment=(
            "路由策略，可选值："
            "manual / hash / weighted / fallback"
        ),
    )

    bucket = Column(
        String(32),
        nullable=True,
        comment="分桶标识",
    )

    group = Column(
        String(32),
        nullable=True,
        comment=(
            "实验分组名称，例如 "
            "control / treatment"
        ),
    )

    weight = Column(
        Float,
        nullable=True,
        comment="命中权重，取值范围 0.0～1.0",
    )

    decision = Column(
        String(32),
        nullable=True,
        comment=(
            "最终决策结果，可选值："
            "approve / reject"
        ),
    )

    context = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "决策上下文，JSON 格式。"
            "可记录路由、实验、Worker 和运行环境等信息"
        ),
    )

    decided_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        server_default=func.now(),
        comment="决策时间，请求完成模型决策的实际时间",
    )

    def __repr__(
            self,
    ) -> str:
        """返回请求决策字符串表示."""
        return (
            f"<Decision("
            f"decision_id='{self.decision_id}', "
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"source='{self.source}'"
            f")>"
        )
