"""批次执行分片表.

记录批次执行尝试拆分出的可独立调度分片及其执行结果，
用于分片状态追踪、任务调度和错误排查。

核心功能：
  - Shard: 批次执行分片记录

使用示例：
  from datamind.db.models.shards import Shard

  shard = Shard(
      shard_id="shd_0123456789abcdef",
      attempt_id="att_0123456789abcdef",
      batch_id="bat_0123456789abcdef",
      task_id="tsk_0123456789abcdef",
      start_index=0,
      end_index=100,
      status="queued",
  )
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
from sqlalchemy.dialects.postgresql import (
    TEXT,
)
from sqlalchemy.sql import func

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Shard(
    IdMixin,
    TimestampMixin,
    Base,
):
    """批次执行分片表."""

    __tablename__ = "shards"

    __table_args__ = (
        Index(
            "uk_shards_shard_id",
            "shard_id",
            unique=True,
        ),
        Index(
            "uk_shards_range",
            "attempt_id",
            "start_index",
            "end_index",
            unique=True,
        ),
        Index(
            "idx_shards_attempt_id",
            "attempt_id",
        ),
        Index(
            "idx_shards_task_id",
            "task_id",
        ),
        CheckConstraint(
            "start_index >= 0 AND end_index > start_index",
            name="range_valid",
        ),
        CheckConstraint(
            "status IN ("
            "'queued', 'running', 'retrying', 'succeeded', "
            "'partially_succeeded', 'failed', 'cancelled'"
            ")",
            name="status_valid",
        ),
    )

    shard_id = Column(
        String(64),
        nullable=False,
        comment="分片 ID，批次执行分片的唯一标识",
    )
    attempt_id = Column(
        String(64),
        nullable=False,
        comment="批次执行尝试 ID",
    )
    batch_id = Column(
        String(64),
        nullable=False,
        comment="批次 ID",
    )
    task_id = Column(
        String(64),
        nullable=False,
        comment="分片执行的 Celery 任务 ID",
    )
    start_index = Column(
        Integer,
        nullable=False,
        comment="起始位置，包含",
    )
    end_index = Column(
        Integer,
        nullable=False,
        comment="结束位置，不包含",
    )
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'queued'"),
        comment=(
            "分片状态，可选值："
            "queued / running / retrying / succeeded / "
            "partially_succeeded / failed / cancelled"
        ),
    )
    worker_id = Column(
        String(255),
        nullable=True,
        comment="实际执行分片任务的 Worker 标识",
    )
    error = Column(
        TEXT,
        nullable=True,
        comment="最近一次执行错误",
    )
    queued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.statement_timestamp(),
        comment="分片入队时间",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="分片执行开始时间",
    )
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="分片执行结束时间",
    )
