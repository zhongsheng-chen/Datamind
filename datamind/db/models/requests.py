# datamind/db/models/requests.py

"""请求表

记录进入系统的原始请求信息，用于请求追踪、异常排查和性能分析。
"""

from sqlalchemy import Column, String, Index, Float, text
from sqlalchemy.dialects.postgresql import JSONB, TEXT

from datamind.db.core import Base, IdMixin, TimestampMixin


class Request(Base, IdMixin, TimestampMixin):
    """请求表"""

    __tablename__ = "requests"

    __table_args__ = (
        Index(
            "idx_requests_request_id",
            "request_id"
        ),
        Index(
            "idx_requests_model_id",
            "model_id"
        ),
        Index(
            "idx_requests_created_at",
            "created_at"
        ),
        Index(
            "idx_requests_source",
            "source"
        ),
        Index(
            "idx_requests_status",
            "status"
        ),
        Index(
            "idx_requests_user",
            "user"
        ),
    )

    request_id = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="请求 ID，请求的唯一标识"
    )
    model_id = Column(
        String(64),
        nullable=False,
        comment="目标模型 ID"
    )
    payload = Column(
        JSONB,
        nullable=True,
        comment="请求负载，JSON 格式"
    )
    source = Column(
        String(50),
        nullable=True,
        comment="请求来源，如 api"
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=text("'received'"),
        comment="请求状态，可选值：received / success / failed"
    )
    error = Column(
        TEXT,
        nullable=True,
        comment="请求处理失败时的错误信息"
    )
    latency_ms = Column(
        Float,
        nullable=True,
        comment="处理耗时，单位毫秒"
    )
    user = Column(
        String(64),
        nullable=True,
        comment="用户标识"
    )
    ip = Column(
        String(64),
        nullable=True,
        comment="客户端 IP 地址"
    )

    def __repr__(self):
        return (
            f"<Request("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"source='{self.source}', "
            f"status='{self.status}'"
            f")>"
        )
