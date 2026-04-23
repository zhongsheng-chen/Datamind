# datamind/db/models/requests.py

"""请求表

记录进入系统的原始请求信息，用于请求追踪和性能分析。
"""

from sqlalchemy import Column, String, Index, JSON, Float

from datamind.db.core import Base, IdMixin, TimestampMixin


class Request(Base, IdMixin, TimestampMixin):
    """请求表

    属性：
        request_id: 请求唯一标识
        user_id: 用户标识（可选）
        model_id: 目标模型ID
        payload: 请求输入（特征/参数）
        source: 请求来源（api/batch/stream）
        ip: 客户端IP地址
        latency_ms: 处理耗时（毫秒）
    """

    __tablename__ = "requests"

    __table_args__ = (
        Index("idx_requests_request_id", "request_id"),
        Index("idx_requests_user_id", "user_id"),
        Index("idx_requests_model_id", "model_id"),
        Index("idx_requests_created_at", "created_at"),
        Index("idx_requests_source", "source"),
    )

    request_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(String(64), nullable=True)

    model_id = Column(String(64), nullable=False)

    payload = Column(JSON, nullable=True)

    source = Column(String(50), nullable=True)
    ip = Column(String(64), nullable=True)

    latency_ms = Column(Float, nullable=True)

    def __repr__(self):
        return f"<Request(request_id='{self.request_id}', model_id='{self.model_id}', source='{self.source}')>"