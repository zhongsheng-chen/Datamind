"""请求表.

记录进入系统的请求及其处理结果，
用于调用追踪、异常排查和性能分析。

核心功能：
  - Request: 原始请求记录

使用示例：
  from datamind.db.models.requests import Request

  request = Request(
      request_id="req_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      model_name="scorecard",
      payload={
          "model_name": "scorecard",
          "environment": "production",
          "deployment_id": "dep_0123456789abcdef",
          "subject_key": "customer_10001",
          "subject_type": "customer",
          "features": {
              "age": 35,
              "annual_income": 120000,
              "debt_to_income_ratio": 0.32,
              "credit_utilization_ratio": 0.45,
              "delinquency_count": 0,
          },
      },
      response={
          "success": True,
          "request_id": "req_0123456789abcdef",
          "decision_id": "dcs_0123456789abcdef",
          "score": 680,
      },
      source="http",
      status="received",
      user="admin",
      ip="192.168.1.100",
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
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


class Request(
    IdMixin,
    TimestampMixin,
    Base,
):
    """请求表."""

    __tablename__ = "requests"

    __table_args__ = (
        Index(
            "idx_requests_model_id",
            "model_id",
        ),
        Index(
            "idx_requests_batch_id",
            "batch_id",
        ),
        Index(
            "idx_requests_model_name",
            "model_name",
        ),
        Index(
            "idx_requests_created_at",
            "created_at",
        ),
        Index(
            "idx_requests_source",
            "source",
        ),
        Index(
            "idx_requests_status",
            "status",
        ),
        Index(
            "idx_requests_user",
            "user",
        ),
        Index(
            "uk_requests_request_id",
            "request_id",
            unique=True,
        ),
        Index(
            "uk_requests_batch_position",
            "batch_id",
            "batch_index",
            unique=True,
            postgresql_where=text(
                "batch_id IS NOT NULL"
            ),
        ),
        CheckConstraint(
            (
                "status IN ("
                "'received', "
                "'success', "
                "'failed'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "latency_ms IS NULL "
                "OR latency_ms >= 0"
            ),
            name="latency_ms_non_negative",
        ),
        CheckConstraint(
            (
                "(batch_id IS NULL AND batch_index IS NULL) "
                "OR (batch_id IS NOT NULL "
                "AND batch_index IS NOT NULL)"
            ),
            name="batch_fields_consistent",
        ),
        CheckConstraint(
            (
                "batch_index IS NULL "
                "OR batch_index >= 0"
            ),
            name="batch_index_non_negative",
        ),
        CheckConstraint(
            (
                "payload IS NULL "
                "OR jsonb_typeof(payload) = 'object'"
            ),
            name="payload_object",
        ),
        CheckConstraint(
            (
                "response IS NULL "
                "OR jsonb_typeof(response) = 'object'"
            ),
            name="response_object",
        ),
    )

    request_id = Column(
        String(64),
        nullable=False,
        comment="请求 ID，请求的唯一标识",
    )

    latest_decision_id = Column(
        String(64),
        nullable=True,
        comment="最近一次决策 ID",
    )

    batch_id = Column(
        String(64),
        nullable=True,
        comment="批次 ID，同一批量预测中的请求共享该标识",
    )

    batch_index = Column(
        Integer,
        nullable=True,
        comment="请求在批量预测中的位置，从 0 开始",
    )

    model_id = Column(
        String(64),
        nullable=True,
        comment="目标模型 ID",
    )

    model_name = Column(
        String(255),
        nullable=True,
        comment="目标模型名称",
    )

    payload = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "请求负载，JSON 格式。"
            "可记录模型、部署、主体和特征等请求信息"
        ),
    )

    response = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "请求处理结果，JSON 格式。"
            "记录返回给调用方的业务响应"
        ),
    )

    source = Column(
        String(50),
        nullable=True,
        comment="请求来源，例如 api",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'received'"
        ),
        comment=(
            "请求状态，可选值："
            "received / success / failed"
        ),
    )

    error = Column(
        TEXT,
        nullable=True,
        comment="请求处理失败时的错误信息",
    )

    latency_ms = Column(
        Float,
        nullable=True,
        comment="处理耗时，单位毫秒",
    )

    user = Column(
        String(64),
        nullable=True,
        comment="用户标识",
    )

    ip = Column(
        String(64),
        nullable=True,
        comment="客户端 IP 地址",
    )

    def __repr__(
            self,
    ) -> str:
        """返回请求记录字符串表示."""
        return (
            f"<Request("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"source='{self.source}', "
            f"status='{self.status}'"
            f")>"
        )
