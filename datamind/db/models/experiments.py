# datamind/db/models/experiments.py

"""AB实验模型
"""

from sqlalchemy import Column, String, JSON

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Experiment(Base, IdMixin, TimestampMixin):
    """AB实验表"""

    __tablename__ = "experiments"

    name = Column(String(64), index=True)
    config = Column(JSON)
    status = Column(String(32))