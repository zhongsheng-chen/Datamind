# datamind/db/models/metadata.py

"""模型元数据模型

存储模型的元数据信息，包括模型标识、类型、Schema和状态等。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表

    属性：
        model_id: 模型唯一标识
        name: 模型名称
        description: 模型描述
        model_type: 模型类型（logistic_regression/decision_tree/random_forest/xgboost/lightgbm/catboost）
        task_type: 任务类型（classification/scoring）
        framework: 框架（sklearn/xgboost/lightgbm/torch/tensorflow/onnx/catboost）
        input_schema: 输入Schema
        output_schema: 输出Schema
        status: 状态（active/inactive/deprecated/archived）
        created_by: 创建人
        updated_by: 更新人
    """

    __tablename__ = "metadata"

    __table_args__ = (
        Index("idx_metadata_name", "name"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_framework", "framework"),
        Index("idx_metadata_model_type", "model_type"),
        Index("idx_metadata_task_type", "task_type"),
        Index("idx_metadata_created_at", "created_at"),
    )

    model_id = Column(String(64), nullable=False, unique=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    model_type = Column(String(50), nullable=False)
    task_type = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    input_schema = Column(JSONB)
    output_schema = Column(JSONB)

    status = Column(String(20), nullable=False, default="active")

    created_by = Column(String(50))
    updated_by = Column(String(50))

    def __repr__(self):
        return f"<Metadata(name='{self.name}', model_id='{self.model_id}', model_type='{self.model_type}')>"