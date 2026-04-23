# datamind/db/models/experiments.py

"""实验表

定义模型版本之间的 AB 实验或灰度策略配置。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Experiment(Base, IdMixin, TimestampMixin):
    """实验表

    属性：
        experiment_id: 实验唯一标识
        model_id: 所属模型ID
        name: 实验名称
        description: 实验描述
        status: 实验状态（running/paused/completed）
        config: 实验配置（策略、变体、权重等）
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        created_by: 创建人
    """

    __tablename__ = "experiments"

    __table_args__ = (
        Index("idx_experiments_model_id", "model_id"),
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created_at", "created_at"),
        Index("idx_experiments_effective_time", "effective_from", "effective_to"),
        Index("idx_experiments_model_id_status", "model_id", "status"),
    )

    experiment_id = Column(String(64), nullable=False, unique=True)
    model_id = Column(String(64), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    status = Column(String(20), nullable=False, default="running")

    config = Column(JSON, nullable=True)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    created_by = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<Experiment(experiment_id='{self.experiment_id}', name='{self.name}', status='{self.status}')>"