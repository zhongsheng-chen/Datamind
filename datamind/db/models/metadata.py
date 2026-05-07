# datamind/db/models/metadata.py

"""模型元数据

存储模型的元数据信息，包括模型标识、类型、Schema 和状态等。
"""

from sqlalchemy import Column, String, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表"""

    __tablename__ = "metadata"

    __table_args__ = (
        Index("idx_metadata_name", "name"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_framework", "framework"),
        Index("idx_metadata_model_type", "model_type"),
        Index("idx_metadata_task_type", "task_type"),
        Index("idx_metadata_created_at", "created_at"),
    )

    model_id = Column(
        String(64), nullable=False, unique=True,
        comment="模型唯一标识"
    )
    name = Column(
        String(100), nullable=False, unique=True,
        comment="模型名称"
    )
    description = Column(
        TEXT, nullable=True,
        comment="模型描述"
    )
    model_type = Column(
        String(50), nullable=False,
        comment="模型类型，可选值：logistic_regression / decision_tree / random_forest / xgboost / lightgbm / catboost"
    )
    task_type = Column(
        String(50), nullable=False,
        comment="任务类型，可选值：classification / scoring"
    )
    framework = Column(
        String(50), nullable=False,
        comment="框架，可选值：sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow"
    )
    input_schema = Column(
        JSONB, nullable=True,
        comment="输入 Schema，JSON 格式"
    )
    output_schema = Column(
        JSONB, nullable=True,
        comment="输出 Schema，JSON 格式"
    )
    status = Column(
        String(20), nullable=False, server_default=text("'active'"),
        comment="状态，可选值：active / inactive / deprecated / archived"
    )
    created_by = Column(
        String(50), nullable=True,
        comment="创建人"
    )
    updated_by = Column(
        String(50), nullable=True,
        comment="更新人"
    )

    def __repr__(self):
        return (
            f"<Metadata("
            f"name='{self.name}', "
            f"model_id='{self.model_id}', "
            f"model_type='{self.model_type}'"
            f")>"
        )