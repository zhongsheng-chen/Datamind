"""控制台事件表

保存控制台实时更新所需的轻量级变更事件，支持断线恢复和事件回放。

核心功能：
  - OutboxEvent: 控制台变更事件

使用示例：
  from datamind.db.models.outbox import OutboxEvent

  event = OutboxEvent(
      topic="models",
      resource_id="mdl_0123456789abcdef",
      action="update",
  )
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.sql import func

from datamind.db.core import Base


class OutboxEvent(Base):
    """控制台变更事件表"""

    __tablename__ = "outbox"

    __table_args__ = (
        Index(
            "idx_outbox_occurred_at",
            "occurred_at",
        ),
        Index(
            "idx_outbox_topic_event_id",
            "topic",
            "event_id",
        ),
        CheckConstraint(
            (
                "topic IN ("
                "'models', "
                "'versions', "
                "'deployments', "
                "'routings', "
                "'runtimes', "
                "'requests', "
                "'decisions', "
                "'executions', "
                "'experiments', "
                "'variants', "
                "'audits'"
                ")"
            ),
            name="topic_valid",
        ),
        CheckConstraint(
            "action IN ('insert', 'update', 'delete')",
            name="action_valid",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name="schema_version_positive",
        ),
    )

    event_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="事件游标",
    )

    topic = Column(
        String(32),
        nullable=False,
        comment="控制台数据主题",
    )

    resource_id = Column(
        String(64),
        nullable=True,
        comment="发生变化的资源 ID",
    )

    action = Column(
        String(16),
        nullable=False,
        comment="变更类型：insert / update / delete",
    )

    schema_version = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="事件结构版本",
    )

    occurred_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        server_default=func.now(),
        comment="事件发生时间",
    )

    def __repr__(
            self,
    ) -> str:
        """返回控制台变更事件字符串表示"""
        return (
            f"<OutboxEvent("
            f"event_id={self.event_id}, "
            f"topic='{self.topic}', "
            f"resource_id='{self.resource_id}', "
            f"action='{self.action}'"
            f")>"
        )
