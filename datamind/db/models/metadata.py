# datamind/db/models/metadata.py

"""模型元数据模型
"""

from sqlalchemy import Column, String, JSON, Boolean

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表"""

    __tablename__ = "metadata"

    model_id = Column(String(64), unique=True, index=True)
    model_type = Column(String(32))
    task_type = Column(String(32))
    framework = Column(String(32))
    is_active = Column(Boolean, default=False)
    params = Column(JSON)
    feature_schema = Column(JSON)