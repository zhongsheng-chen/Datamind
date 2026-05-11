# datamind/db/models/experiments.py

"""实验配置表

定义模型版本之间的可复现对比实验，用于在一致流量条件下进行模型效果验证。
"""

from sqlalchemy import Column, String, Text, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Experiment(Base, IdMixin, TimestampMixin):
    """实验表"""

    __tablename__ = "experiments"

    __table_args__ = (
        Index("idx_experiments_model_id", "model_id"),
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created_at", "created_at"),
        Index("idx_experiments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("idx_experiments_model_id_status", "model_id", "status"),
        Index("uk_experiments_experiment_id", "experiment_id", unique=True),
    )

    experiment_id = Column(
        String(64), nullable=False,
        comment="实验 ID，实验的唯一标识"
    )
    model_id = Column(
        String(64), nullable=False,
        comment="模型 ID"
    )
    name = Column(
        String(100), nullable=True,
        comment="实验名称"
    )
    description = Column(
        Text, nullable=True,
        comment="实验描述"
    )
    status = Column(
        String(20), nullable=False, server_default=text("'draft'"),
        comment="实验状态，可选值：draft / running / paused / stopped / completed"
    )
    config = Column(
        JSONB, nullable=True,
        comment="实验配置，JSON 格式。包含流量分配策略、实验变体及权重配置等，仅用于跟踪和调试"
    )
    effective_from = Column(
        DateTime(timezone=True), nullable=True,
        comment="生效开始时间"
    )
    effective_to = Column(
        DateTime(timezone=True), nullable=True,
        comment="生效结束时间"
    )
    created_by = Column(
        String(50), nullable=True,
        comment="创建人"
    )

    def __repr__(self):
        return (
            f"<Experiment("
            f"experiment_id='{self.experiment_id}', "
            f"model_id='{self.model_id}', "
            f"name='{self.name}', "
            f"status='{self.status}'"
            f")>"
        )