"""实验配置表.

记录模型在指定环境中的对比实验配置，
用于定义实验生命周期、生效时间和实验参数。

核心功能：
  - Experiment: 实验配置记录

使用示例：
  from datamind.db.models.experiments import Experiment

  experiment = Experiment(
      experiment_id="exp_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      environment="production",
      name="scorecard_ab_test",
      config={
          "strategy": "hash",
          "traffic_ratio": 0.3,
          "bucket_key": "customer_id",
      },
      created_by="admin",
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Experiment(
    IdMixin,
    TimestampMixin,
    Base,
):
    """实验配置表."""

    __tablename__ = "experiments"

    __table_args__ = (
        Index(
            "idx_experiments_model_id",
            "model_id",
        ),
        Index(
            "idx_experiments_environment",
            "environment",
        ),
        Index(
            "idx_experiments_status",
            "status",
        ),
        Index(
            "idx_experiments_created_at",
            "created_at",
        ),
        Index(
            "idx_experiments_deleted_at",
            "deleted_at",
        ),
        Index(
            "idx_experiments_effective_time",
            "model_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "idx_experiments_model_environment_effective_time",
            "model_id",
            "environment",
            "effective_from",
            "effective_to",
        ),
        Index(
            "idx_experiments_model_id_status",
            "model_id",
            "status",
        ),
        Index(
            "idx_experiments_model_environment_status",
            "model_id",
            "environment",
            "status",
        ),
        Index(
            "uk_experiments_running_model_environment",
            "model_id",
            "environment",
            unique=True,
            postgresql_where=text(
                "status = 'running' "
                "AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uk_experiments_experiment_id",
            "experiment_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "environment IN ("
                "'development', "
                "'testing', "
                "'staging', "
                "'production'"
                ")"
            ),
            name="environment_valid",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'draft', "
                "'running', "
                "'paused', "
                "'stopped', "
                "'completed', "
                "'archived'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "config IS NULL "
                "OR jsonb_typeof(config) = 'object'"
            ),
            name="config_valid",
        ),
        CheckConstraint(
            (
                "effective_to IS NULL "
                "OR effective_from IS NULL "
                "OR effective_to > effective_from"
            ),
            name="effective_time_valid",
        ),
    )

    experiment_id = Column(
        String(64),
        nullable=False,
        comment="实验 ID，实验的唯一标识",
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID",
    )

    environment = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'development'"
        ),
        comment=(
            "实验环境，可选值："
            "development / testing / staging / production"
        ),
    )

    name = Column(
        String(100),
        nullable=True,
        comment="实验名称",
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="实验描述",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'draft'"
        ),
        comment=(
            "实验状态，可选值："
            "draft / running / paused / stopped / completed / archived"
        ),
    )

    config = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "实验配置，JSON 对象，包含实验曝光比例、"
            "分桶字段和策略参数等信息"
        ),
    )

    effective_from = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="生效时间",
    )

    effective_to = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="失效时间",
    )

    created_by = Column(
        String(50),
        nullable=True,
        comment="创建人",
    )

    updated_by = Column(
        String(50),
        nullable=True,
        comment="更新人",
    )

    deleted_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="逻辑删除时间",
    )

    deleted_by = Column(
        String(50),
        nullable=True,
        comment="逻辑删除操作人",
    )

    deletion_id = Column(
        String(64),
        nullable=True,
        comment="逻辑删除批次 ID",
    )

    deletion_reason = Column(
        TEXT,
        nullable=True,
        comment="逻辑删除原因",
    )

    def __repr__(
            self,
    ) -> str:
        """返回实验配置字符串表示."""
        return (
            f"<Experiment("
            f"experiment_id='{self.experiment_id}', "
            f"model_id='{self.model_id}', "
            f"environment='{self.environment}', "
            f"name='{self.name}', "
            f"status='{self.status}'"
            f")>"
        )
