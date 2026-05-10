# datamind/db/models/versions.py

"""模型版本

存储模型版本信息，每次模型注册生成一条记录。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表"""

    __tablename__ = "versions"

    __table_args__ = (
        Index("idx_versions_model_id", "model_id"),
        Index("idx_versions_framework", "framework"),
        Index("idx_versions_bento_tag", "bento_tag"),
        Index("idx_versions_created_at", "created_at"),
        Index("uk_versions_model_id_version", "model_id", "version", unique=True),
    )

    model_id = Column(
        String(64), nullable=False,
        comment="所属模型 ID"
    )
    version = Column(
        String(50), nullable=False,
        comment="版本号"
    )
    framework = Column(
        String(50), nullable=False,
        comment="模型框架，如 sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow"
    )
    bento_tag = Column(
        String(100), nullable=False,
        comment="BentoML 标签，格式为 模型名:版本"
    )
    model_path = Column(
        String(255), nullable=False,
        comment="模型文件存储路径"
    )
    storage_key = Column(
        String(255), nullable=False,
        comment="存储键，模型文件在存储空间中的唯一标识"
    )
    params = Column(
        JSONB, nullable=True,
        comment="模型参数，JSON 格式"
    )
    metrics = Column(
        JSONB, nullable=True,
        comment="模型评估指标，JSON 格式"
    )
    description = Column(
        Text, nullable=True,
        comment="版本说明"
    )
    created_by = Column(
        String(50), nullable=True,
        comment="创建人"
    )

    def __repr__(self):
        return (
            f"<Version("
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )