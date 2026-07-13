# datamind/db/models/requests.py

"""请求表

记录进入系统的原始请求信息，
用于请求追踪、异常排查和性能分析。

核心功能：
  - Request: 原始请求记录

使用示例：
  from datamind.db.models.requests import Request

  request = Request(
      request_id="req_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      payload={
          "model_id": "mdl_0123456789abcdef",
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
    """请求表"""

    __tablename__ = "requests"

    __table_args__ = (
        Index(
            "idx_requests_model_id",
            "model_id",
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
                "payload IS NULL "
                "OR jsonb_typeof(payload) = 'object'"
            ),
            name="payload_object",
        ),
    )

    request_id = Column(
        String(64),
        nullable=False,
        comment="请求 ID，请求的唯一标识",
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="目标模型 ID",
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
        """返回请求记录字符串表示"""
        return (
            f"<Request("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"source='{self.source}', "
            f"status='{self.status}'"
            f")>"
        )
