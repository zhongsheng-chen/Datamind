# datamind/db/models/requests.py

"""API调用日志模型
"""

from sqlalchemy import Column, String, Integer, JSON

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Request(Base, IdMixin, TimestampMixin):
    """API调用日志表"""

    __tablename__ = "requests"

    request_id = Column(String(64), unique=True, index=True)
    model_id = Column(String(64), index=True)
    model_version = Column(String(32))
    endpoint = Column(String(128))
    status_code = Column(Integer)
    latency_ms = Column(Integer)
    request_data = Column(JSON)
    response_data = Column(JSON)