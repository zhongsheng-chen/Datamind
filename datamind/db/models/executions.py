"""模型执行表.

记录产生最终决策的主模型执行和异步影子模型执行，
用于执行状态追踪、结果比较、异常排查和性能分析。

核心功能：
  - Execution: 模型执行记录

使用示例：
  from datamind.db.models.executions import Execution

  execution = Execution(
      execution_id="exe_0123456789abcdef",
      decision_id="dcs_0123456789abcdef",
      execution_type="shadow",
      status="queued",
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      deployment_id="dep_0123456789abcdef",
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
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Execution(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型执行记录表."""

    __tablename__ = "executions"

    __table_args__ = (
        Index(
            "idx_executions_decision_id",
            "decision_id",
        ),
        Index(
            "idx_executions_deployment_id",
            "deployment_id",
        ),
        Index(
            "idx_executions_model_id",
            "model_id",
        ),
        Index(
            "idx_executions_status",
            "status",
        ),
        Index(
            "idx_executions_type_status",
            "execution_type",
            "status",
        ),
        Index(
            "idx_executions_created_at",
            "created_at",
        ),
        Index(
            "uk_executions_execution_id",
            "execution_id",
            unique=True,
        ),
        Index(
            "uk_executions_decision_deployment",
            "decision_id",
            "deployment_id",
            unique=True,
        ),
        Index(
            "uk_executions_primary_decision",
            "decision_id",
            unique=True,
            postgresql_where=text(
                "execution_type = 'primary'"
            ),
        ),
        CheckConstraint(
            "execution_type IN ('primary', 'shadow')",
            name="execution_type_valid",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'queued', "
                "'running', "
                "'success', "
                "'failed', "
                "'timeout', "
                "'cancelled'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "probability IS NULL "
                "OR (probability >= 0 AND probability <= 1)"
            ),
            name="probability_range",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="latency_ms_non_negative",
        ),
        CheckConstraint(
            (
                "prediction IS NULL "
                "OR jsonb_typeof(prediction) = 'object'"
            ),
            name="prediction_object",
        ),
        CheckConstraint(
            (
                "context IS NULL "
                "OR jsonb_typeof(context) = 'object'"
            ),
            name="context_object",
        ),
        CheckConstraint(
            (
                "(status IN ('queued', 'running') "
                "AND finished_at IS NULL) "
                "OR (status NOT IN ('queued', 'running') "
                "AND finished_at IS NOT NULL)"
            ),
            name="unfinished_status_valid",
        ),
    )

    execution_id = Column(
        String(64),
        nullable=False,
        comment="执行 ID，模型执行记录的唯一标识",
    )

    decision_id = Column(
        String(64),
        nullable=False,
        comment="决策 ID",
    )

    execution_type = Column(
        String(20),
        nullable=False,
        comment=(
            "执行类型，可选值："
            "primary / shadow"
        ),
    )

    status = Column(
        String(20),
        nullable=False,
        comment=(
            "执行状态，可选值："
            "queued / running / success / failed / timeout / cancelled"
        ),
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="执行使用的模型 ID",
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="执行使用的版本 ID",
    )

    deployment_id = Column(
        String(64),
        nullable=True,
        comment="执行使用的部署 ID，可选",
    )

    routing_id = Column(
        String(64),
        nullable=True,
        comment="命中的路由 ID",
    )

    prediction = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="模型预测结果，JSON 格式",
    )

    probability = Column(
        Float,
        nullable=True,
        comment="预测概率，取值范围 0.0～1.0",
    )

    score = Column(
        Float,
        nullable=True,
        comment="评分结果",
    )

    latency_ms = Column(
        Float,
        nullable=True,
        comment="执行耗时，单位毫秒",
    )

    error_type = Column(
        String(128),
        nullable=True,
        comment="执行失败时的错误类型",
    )

    error = Column(
        TEXT,
        nullable=True,
        comment="执行失败时的错误信息",
    )

    context = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="模型执行上下文，JSON 格式",
    )

    started_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="执行开始时间",
    )

    finished_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="执行结束时间",
    )

    def __repr__(
            self,
    ) -> str:
        """返回模型执行记录的字符串表示."""
        return (
            f"<Execution("
            f"execution_id='{self.execution_id}', "
            f"decision_id='{self.decision_id}', "
            f"execution_type='{self.execution_type}', "
            f"status='{self.status}', "
            f"deployment_id='{self.deployment_id}'"
            f")>"
        )
