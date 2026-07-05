# datamind/db/models/outcomes.py

"""实验结果表

记录请求或实验分配主体的后验结果，
用于 A/B 测试效果评估、模型表现监控和业务指标统计。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Outcome(Base, IdMixin, TimestampMixin):
    """实验结果表"""

    __tablename__ = "outcomes"

    __table_args__ = (
        Index(
            "idx_outcomes_experiment_id",
            "experiment_id"
        ),
        Index(
            "idx_outcomes_variant_id",
            "variant_id"
        ),
        Index(
            "idx_outcomes_assignment_id",
            "assignment_id"
        ),
        Index(
            "idx_outcomes_decision_id",
            "decision_id"
        ),
        Index(
            "idx_outcomes_request_id",
            "request_id"
        ),
        Index(
            "idx_outcomes_subject_key",
            "subject_key"
        ),
        Index(
            "idx_outcomes_outcome_time",
            "outcome_time"
        ),
        Index(
            "idx_outcomes_created_at",
            "created_at"
        ),
        Index(
            "uk_outcomes_outcome_id",
            "outcome_id",
            unique=True
        ),
    )

    outcome_id = Column(
        String(64),
        nullable=False,
        comment="结果 ID，实验结果记录的唯一标识"
    )
    experiment_id = Column(
        String(64),
        nullable=True,
        comment="实验 ID"
    )
    variant_id = Column(
        String(64),
        nullable=True,
        comment="实验分组 ID"
    )
    assignment_id = Column(
        String(64),
        nullable=True,
        comment="实验分配 ID"
    )
    decision_id = Column(
        String(64),
        nullable=True,
        comment="请求决策 ID"
    )
    request_id = Column(
        String(64),
        nullable=True,
        comment="请求 ID"
    )
    subject_key = Column(
        String(128),
        nullable=False,
        comment="结果主体标识，例如客户号、订单号、申请单号"
    )
    subject_type = Column(
        String(32),
        nullable=True,
        comment="结果主体类型，例如 customer / order / application"
    )
    approved = Column(
        Boolean,
        nullable=True,
        comment="是否审批通过"
    )
    converted = Column(
        Boolean,
        nullable=True,
        comment="是否转化，例如是否放款、是否签约、是否支用"
    )
    defaulted = Column(
        Boolean,
        nullable=True,
        comment="是否违约或成为坏样本"
    )
    overdue_days = Column(
        Integer,
        nullable=True,
        comment="最大逾期天数"
    )
    amount = Column(
        Float,
        nullable=True,
        comment="结果金额，例如审批金额、放款金额、支用金额"
    )
    label = Column(
        String(32),
        nullable=True,
        comment="结果标签，例如 good / bad / unknown"
    )
    context = Column(
        JSONB,
        nullable=True,
        comment="结果上下文，JSON 格式。包含业务结果、观测窗口、回流来源等信息"
    )
    outcome_time = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="结果发生时间"
    )

    def __repr__(self):
        return (
            f"<Outcome("
            f"outcome_id='{self.outcome_id}', "
            f"experiment_id='{self.experiment_id}', "
            f"variant_id='{self.variant_id}', "
            f"subject_key='{self.subject_key}'"
            f")>"
        )