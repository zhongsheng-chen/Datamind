# datamind/db/models/assignments.py

"""AB分流模型
"""

from sqlalchemy import Column, String, Integer

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """AB分流表"""

    __tablename__ = "assignments"

    experiment_id = Column(String(64), index=True)
    model_id = Column(String(64))
    traffic_ratio = Column(Integer)  # 0-100