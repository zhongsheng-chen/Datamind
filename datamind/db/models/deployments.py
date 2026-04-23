# datamind/db/models/deployments.py

"""模型部署模型
"""

from sqlalchemy import Column, String, Boolean

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表"""

    __tablename__ = "deployments"

    model_id = Column(String(64), index=True)
    version = Column(String(32))
    status = Column(String(32))  # running / stopped
    endpoint = Column(String(128))