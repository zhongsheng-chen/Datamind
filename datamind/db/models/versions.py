# datamind/db/models/versions.py

"""模型版本表

存储模型版本信息，包含模型产物及其运行框架与状态信息。
"""

from sqlalchemy import Column, String, Text, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表"""

    __tablename__ = "versions"

    __table_args__ = (
        Index("idx_versions_model_id", "model_id"),
        Index("idx_versions_framework", "framework"),
        Index("idx_versions_status", "status"),
        Index("idx_versions_created_at", "created_at"),
        Index("uk_versions_model_id_version", "model_id", "version", unique=True),
        Index("uk_versions_version_id", "version_id", unique=True),
    )

    version_id = Column(
        String(64), nullable=False,
        comment="版本 ID，模型版本的唯一标识"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="模型 ID"
    )
    version = Column(
        String(50), nullable=False,
        comment="版本号"
    )
    framework = Column(
        String(50), nullable=False,
        comment="框架类型，如 sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow"
    )
    status = Column(
        String(20), nullable=False, server_default=text("'active'"),
        comment="状态，可选值：active / deprecated / archived"
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
    updated_by = Column(
        String(50), nullable=True,
        comment="更新人"
    )
    deleted_at = Column(
        DateTime(timezone=True), nullable=True,
        comment="删除时间"
    )
    deleted_by = Column(
        String(50), nullable=True,
        comment="删除人"
    )
    archived_at = Column(
        DateTime(timezone=True), nullable=True,
        comment="归档时间"
    )
    archived_by = Column(
        String(50), nullable=True,
        comment="归档人"
    )

    def __repr__(self):
        return (
            f"<Version("
            f"version_id='{self.version_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )