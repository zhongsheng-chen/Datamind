# datamind/db/models/metadata.py

"""模型元数据表

存储模型的元数据信息，包含模型标识、类型、框架和状态等基础信息。
"""

from sqlalchemy import Column, String, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表"""

    __tablename__ = "metadata"

    __table_args__ = (
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_framework", "framework"),
        Index("idx_metadata_model_type", "model_type"),
        Index("idx_metadata_task_type", "task_type"),
        Index("idx_metadata_created_at", "created_at"),
        Index("uk_metadata_model_id", "model_id", unique=True),
        Index("uk_metadata_name", "name", unique=True),
    )

    model_id = Column(
        String(64), nullable=False,
        comment="模型 ID，模型的唯一标识"
    )
    name = Column(
        String(100), nullable=False,
        comment="模型名称，全局唯一业务标识"
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
        comment="框架类型，可选值：sklearn / xgboost / lightgbm / catboost / torch / onnx / tensorflow"
    )
    description = Column(
        TEXT, nullable=True,
        comment="模型描述"
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
        String(20), nullable=False, server_default=text("'inactive'"),
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