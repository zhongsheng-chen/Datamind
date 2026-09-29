"""审计日志表.

记录系统控制平面的变更行为，
用于操作追溯、问题排查和审计分析。

核心功能：
  - Audit: 审计日志记录

使用示例：
  from datamind.db.models.audit import Audit

  audit = Audit(
      audit_id="aud_0123456789abcdef",
      action="model.register",
      resource="model",
      operation="register",
      target_type="model",
      target_id="mdl_0123456789abcdef",
      source="cli",
      trace_id="0123456789abcdef0123456789abcdef",
      request_id="req_0123456789abcdef",
      user="admin",
      ip="192.168.1.100",
      hostname="client",
      status="success",
      before=None,
      after={
          "name": "scorecard",
          "version": "1.0.0",
          ...
      },
      context={
          "operator": "admin",
          ...
      },
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)
from sqlalchemy.sql import func

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Audit(
    IdMixin,
    TimestampMixin,
    Base,
):
    """审计日志表."""

    __tablename__ = "audit"

    __table_args__ = (
        Index(
            "idx_audit_target_id_occurred_at",
            "target_type",
            "target_id",
            "occurred_at",
        ),
        Index(
            "idx_audit_trace_id_occurred_at",
            "trace_id",
            "occurred_at",
            postgresql_where=text(
                "trace_id IS NOT NULL"
            ),
        ),
        Index(
            "idx_audit_request_id_occurred_at",
            "request_id",
            "occurred_at",
            postgresql_where=text(
                "request_id IS NOT NULL"
            ),
        ),
        Index(
            "idx_audit_user_occurred_at",
            "user",
            "occurred_at",
        ),
        Index(
            "idx_audit_target_type_occurred_at",
            "target_type",
            "occurred_at",
        ),
        Index(
            "idx_audit_failed_occurred_at",
            "occurred_at",
            postgresql_where=text(
                "status = 'failed'"
            ),
        ),
        Index(
            "idx_audit_source_occurred_at",
            "source",
            "occurred_at",
        ),
        Index(
            "idx_audit_occurred_at",
            "occurred_at",
        ),
        Index(
            "uk_audit_audit_id",
            "audit_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "source IN ("
                "'http', "
                "'cli', "
                "'system', "
                "'worker', "
                "'scheduler'"
                ")"
            ),
            name="source_valid",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'success', "
                "'failed'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "context IS NULL "
                "OR jsonb_typeof(context) = 'object'"
            ),
            name="context_object",
        ),
    )

    audit_id = Column(
        String(64),
        nullable=False,
        comment="审计 ID，审计事件的唯一标识",
    )

    action = Column(
        String(64),
        nullable=False,
        comment=(
            "操作类型，格式为 resource.operation，"
            "例如 model.register"
        ),
    )

    resource = Column(
        String(64),
        nullable=False,
        comment="发起当前操作的业务资源类型",
    )

    operation = Column(
        String(64),
        nullable=False,
        comment="操作名称，例如 register / create / delete / update",
    )

    target_type = Column(
        String(64),
        nullable=False,
        comment="当前操作实际作用的目标类型",
    )

    target_id = Column(
        String(64),
        nullable=False,
        comment="目标 ID",
    )

    source = Column(
        String(16),
        nullable=False,
        server_default=text(
            "'system'"
        ),
        comment=(
            "来源类型，可选值："
            "http / cli / system / worker / scheduler"
        ),
    )

    trace_id = Column(
        String(64),
        nullable=True,
        comment="链路追踪 ID",
    )

    request_id = Column(
        String(64),
        nullable=True,
        comment="触发当前审计事件的请求 ID",
    )

    user = Column(
        String(64),
        nullable=True,
        server_default=text(
            "'system'"
        ),
        comment="操作者",
    )

    ip = Column(
        String(64),
        nullable=True,
        comment="客户端 IP 地址",
    )

    hostname = Column(
        String(128),
        nullable=True,
        comment="客户端主机名称",
    )

    status = Column(
        String(16),
        nullable=False,
        server_default=text(
            "'success'"
        ),
        comment=(
            "操作状态，可选值："
            "success / failed"
        ),
    )

    error = Column(
        TEXT,
        nullable=True,
        comment="错误信息",
    )

    before = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="变更前数据，JSON 格式",
    )

    after = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="变更后数据，JSON 格式",
    )

    context = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "操作上下文，JSON 格式。"
            "可记录调用参数、操作人和扩展信息等"
        ),
    )

    occurred_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        server_default=func.now(),
        comment="操作发生时间",
    )

    def __repr__(
            self,
    ) -> str:
        """返回审计日志字符串表示."""
        return (
            f"<Audit("
            f"audit_id='{self.audit_id}', "
            f"action='{self.action}', "
            f"target_type='{self.target_type}', "
            f"target_id='{self.target_id}', "
            f"status='{self.status}'"
            f")>"
        )
