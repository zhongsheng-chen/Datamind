# datamind/db/models/versions.py

"""模型版本模型
"""

from sqlalchemy import Column, String, JSON

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表"""

    __tablename__ = "versions"

    model_id = Column(String(64), index=True)
    version = Column(String(32), index=True)
    artifact_path = Column(String(256))
    metrics = Column(JSON)