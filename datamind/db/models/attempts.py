"""批次执行尝试表.

记录预测批次每次进入 Worker 的调度与执行结果，
用于查看自动重试和人工重试形成的完整执行历史。

核心功能：
  - Attempt: 批次执行尝试记录
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TEXT
from sqlalchemy.sql import func

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Attempt(
    IdMixin,
    TimestampMixin,
    Base,
):
    """批次执行尝试表."""

    __tablename__ = "attempts"

    __table_args__ = (
        Index(
            "uk_attempts_attempt_id",
            "attempt_id",
            unique=True,
        ),
        Index(
            "uk_attempts_batch_number",
            "batch_id",
            "attempt_number",
            unique=True,
        ),
        Index(
            "idx_attempts_task_id",
            "task_id",
        ),
        Index(
            "idx_attempts_status_created_at",
            "status",
            "created_at",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="attempt_number_positive",
        ),
        CheckConstraint(
            "status IN ("
            "'queued', 'running', 'succeeded', "
            "'partially_succeeded', 'failed', 'cancelled'"
            ")",
            name="status_valid",
        ),
        CheckConstraint(
            "(status IN ('queued', 'running') AND finished_at IS NULL) "
            "OR (status NOT IN ('queued', 'running') "
            "AND finished_at IS NOT NULL)",
            name="finished_status_valid",
        ),
    )

    attempt_id = Column(
        String(64),
        nullable=False,
        comment="执行尝试 ID，批次单次执行的唯一标识",
    )
    batch_id = Column(
        String(64),
        nullable=False,
        comment="批次 ID",
    )
    task_id = Column(
        String(64),
        nullable=False,
        comment="批次执行的 Celery 任务 ID",
    )
    attempt_number = Column(
        Integer,
        nullable=False,
        comment="批次执行序号，从 1 开始",
    )
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'queued'"),
        comment=(
            "执行状态，可选值："
            "queued / running / succeeded / partially_succeeded / "
            "failed / cancelled"
        ),
    )
    worker_id = Column(
        String(255),
        nullable=True,
        comment="实际执行任务的 Worker 标识",
    )
    error = Column(
        TEXT,
        nullable=True,
        comment="本次执行失败原因",
    )
    retry_scheduled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="自动重试时间",
    )
    queued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.statement_timestamp(),
        comment="本次执行进入任务队列的时间",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="本次执行开始时间",
    )
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="本次执行结束时间",
    )
