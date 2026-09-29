"""预测批次表.

记录异步批量预测请求及其调度和执行结果，
用于批次状态追踪、任务取消、失败重试和结果查询。

核心功能：
  - Batch: 预测批次记录

使用示例：
  from datamind.db.models.batches import Batch

  batch = Batch(
      batch_id="bat_0123456789abcdef",
      task_id="tsk_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      model_name="scorecard",
      environment="production",
      status="queued",
      payload={
          "model_name": "scorecard",
          "instances": [
              {
                  "subject_key": "customer_10001",
                  "subject_type": "customer",
                  "features": {
                      "age": 35,
                      "annual_income": 120000,
                  },
              },
          ],
      },
      total_count=1,
      source="http",
      user="admin",
      ip="192.168.1.100",
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
    JSONB,
    TEXT,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Batch(
    IdMixin,
    TimestampMixin,
    Base,
):
    """预测批次表."""

    __tablename__ = "batches"

    __table_args__ = (
        Index(
            "uk_batches_batch_id",
            "batch_id",
            unique=True,
        ),
        Index(
            "uk_batches_task_id",
            "task_id",
            unique=True,
        ),
        Index(
            "idx_batches_status_created_at",
            "status",
            "created_at",
        ),
        CheckConstraint(
            "status IN ("
            "'queued', 'running', 'retrying', 'succeeded', "
            "'partially_succeeded', 'failed', "
            "'cancelling', 'cancelled'"
            ")",
            name="status_valid",
        ),
        CheckConstraint(
            "total_count >= 1",
            name="total_count_positive",
        ),
        CheckConstraint(
            "completed_count >= 0 "
            "AND succeeded_count >= 0 "
            "AND failed_count >= 0",
            name="counts_non_negative",
        ),
        CheckConstraint(
            "completed_count <= total_count "
            "AND succeeded_count + failed_count <= total_count",
            name="counts_within_total",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="attempt_count_non_negative",
        ),
    )

    batch_id = Column(
        String(64),
        nullable=False,
        comment="批次 ID，批量预测的唯一标识",
    )
    task_id = Column(
        String(64),
        nullable=False,
        comment="当前 Celery 任务 ID",
    )
    model_id = Column(
        String(64),
        nullable=True,
        comment="目标模型 ID",
    )
    model_name = Column(
        String(100),
        nullable=False,
        comment="目标模型名称",
    )
    deployment_id = Column(
        String(64),
        nullable=True,
        comment="调用方指定的部署 ID",
    )
    environment = Column(
        String(32),
        nullable=False,
        comment="运行环境",
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=text("'queued'"),
        comment=(
            "批次状态，可选值："
            "queued / running / retrying / succeeded / "
            "partially_succeeded / failed / cancelling / cancelled"
        ),
    )
    payload = Column(
        JSONB(none_as_null=True),
        nullable=False,
        comment="批量预测请求负载",
    )
    result = Column(
        JSONB(none_as_null=True),
        nullable=True,
        comment="批量预测最终结果",
    )
    error = Column(
        TEXT,
        nullable=True,
        comment="批次执行或调度失败原因",
    )
    total_count = Column(
        Integer,
        nullable=False,
        comment="批次总记录数",
    )
    completed_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="已完成记录数",
    )
    succeeded_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="成功记录数",
    )
    failed_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="失败记录数",
    )
    attempt_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="执行尝试次数",
    )
    cancel_requested_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="取消请求时间",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次执行开始时间",
    )
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="批次结束时间",
    )
    source = Column(
        String(50),
        nullable=True,
        comment="请求来源",
    )
    user = Column(
        String(64),
        nullable=True,
        comment="提交用户",
    )
    ip = Column(
        String(64),
        nullable=True,
        comment="提交方 IP 地址",
    )
