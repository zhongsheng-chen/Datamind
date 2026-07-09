# datamind/db/models/decisions.py

"""请求决策表

记录每个请求最终命中的模型版本、部署、实验分组和模型输出，
用于在线推理、A/B 测试、灰度发布和决策审计。
"""

from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from datamind.db.core import Base, IdMixin, TimestampMixin


class Decision(Base, IdMixin, TimestampMixin):
    """请求决策记录表"""

    __tablename__ = "decisions"

    __table_args__ = (
        Index(
            "idx_decisions_model_id",
            "model_id"
        ),
        Index(
            "idx_decisions_version_id",
            "version_id"
        ),
        Index(
            "idx_decisions_deployment_id",
            "deployment_id"
        ),
        Index(
            "idx_decisions_experiment_id",
            "experiment_id"
        ),
        Index(
            "idx_decisions_variant_id",
            "variant_id"
        ),
        Index(
            "idx_decisions_assignment_id",
            "assignment_id"
        ),
        Index(
            "idx_decisions_subject_key",
            "subject_key"
        ),
        Index(
            "idx_decisions_created_at",
            "created_at"
        ),
        Index(
            "idx_decisions_source",
            "source"
        ),
        Index(
            "uk_decisions_decision_id",
            "decision_id",
            unique=True
        ),
        Index(
            "uk_decisions_request_id",
            "request_id",
            unique=True
        ),
    )

    decision_id = Column(
        String(64),
        nullable=False,
        comment="决策 ID，决策记录的唯一标识"
    )
    request_id = Column(
        String(64),
        nullable=False,
        comment="请求 ID"
    )
    model_id = Column(
        String(64),
        nullable=False,
        comment="命中的模型 ID"
    )
    version_id = Column(
        String(64),
        nullable=False,
        comment="命中的版本 ID"
    )
    deployment_id = Column(
        String(64),
        nullable=True,
        comment="命中的部署 ID"
    )
    experiment_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验 ID"
    )
    variant_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验分组 ID"
    )
    assignment_id = Column(
        String(64),
        nullable=True,
        comment="命中的实验分配 ID"
    )
    subject_key = Column(
        String(128),
        nullable=True,
        comment="请求主体标识，例如客户号、订单号、申请单号"
    )
    subject_type = Column(
        String(32),
        nullable=True,
        comment="请求主体类型，例如 customer / order / application"
    )
    source = Column(
        String(20),
        nullable=False,
        comment="决策来源，可选值：experiment / routing / deployment / shadow / manual"
    )
    strategy = Column(
        String(20),
        nullable=True,
        comment="流量分配策略，可选值：manual / random / hash / bucket / weighted"
    )
    bucket = Column(
        String(32),
        nullable=True,
        comment="分桶标识"
    )
    group = Column(
        String(32),
        nullable=True,
        comment="实验分组名称，如 control / treatment"
    )
    weight = Column(
        Float,
        nullable=True,
        comment="命中分组的权重"
    )
    prediction = Column(
        JSONB,
        nullable=True,
        comment="模型预测结果，JSON 格式"
    )
    probability = Column(
        Float,
        nullable=True,
        comment="预测概率"
    )
    score = Column(
        Float,
        nullable=True,
        comment="评分结果"
    )
    decision = Column(
        String(32),
        nullable=True,
        comment="最终决策结果，如 approve / reject / review"
    )
    latency_ms = Column(
        Float,
        nullable=True,
        comment="决策耗时，单位毫秒"
    )
    context = Column(
        JSONB,
        nullable=True,
        comment="决策上下文，JSON 格式。包含路由、实验、模型输出等调试信息"
    )
    decided_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="决策时间，表示请求完成模型决策的实际时间"
    )

    def __repr__(self):
        return (
            f"<Decision("
            f"decision_id='{self.decision_id}', "
            f"request_id='{self.request_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}'"
            f")>"
        )
