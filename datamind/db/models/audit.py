# datamind/db/models/audit.py

"""审计日志模型
"""

from sqlalchemy import Column, String, JSON

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表"""

    __tablename__ = "audit"

    action = Column(String(64), index=True)
    operator = Column(String(64))
    model_id = Column(String(64), index=True)
    model_version = Column(String(32))
    payload = Column(JSON)