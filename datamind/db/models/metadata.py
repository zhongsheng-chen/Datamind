"""模型元数据表.

存储模型的基础元数据信息，包括模型标识、模型类型、
任务类型、框架、状态和生命周期记录。

核心功能：
  - Metadata: 模型元数据记录

使用示例：
  from datamind.db.models.metadata import Metadata

  metadata = Metadata(
      model_id="mdl_0123456789abcdef",
      name="scorecard",
      model_type="logistic_regression",
      task_type="scoring",
      framework="sklearn",
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
from sqlalchemy.dialects.postgresql import TEXT

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Metadata(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型元数据表."""

    __tablename__ = "metadata"

    __table_args__ = (
        Index(
            "idx_metadata_status",
            "status",
        ),
        Index(
            "idx_metadata_framework",
            "framework",
        ),
        Index(
            "idx_metadata_model_type",
            "model_type",
        ),
        Index(
            "idx_metadata_task_type",
            "task_type",
        ),
        Index(
            "idx_metadata_created_at",
            "created_at",
        ),
        Index(
            "uk_metadata_model_id",
            "model_id",
            unique=True,
        ),
        Index(
            "uk_metadata_name",
            "name",
            unique=True,
        ),
        CheckConstraint(
            (
                "model_type IN ("
                "'logistic_regression', "
                "'decision_tree', "
                "'random_forest', "
                "'xgboost', "
                "'lightgbm', "
                "'catboost'"
                ")"
            ),
            name="model_type_valid",
        ),
        CheckConstraint(
            "task_type IN ('classification', 'scoring')",
            name="task_type_valid",
        ),
        CheckConstraint(
            (
                "framework IN ("
                "'sklearn', "
                "'xgboost', "
                "'lightgbm', "
                "'catboost'"
                ")"
            ),
            name="framework_valid",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'deprecated', "
                "'inactive', "
                "'archived'"
                ")"
            ),
            name="status_valid",
        ),
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID，模型的唯一标识",
    )

    name = Column(
        String(100),
        nullable=False,
        comment="模型名称，全局唯一业务标识",
    )

    display_name = Column(
        String(100),
        nullable=True,
        comment="模型显示名称",
    )

    model_type = Column(
        String(50),
        nullable=False,
        comment=(
            "模型类型，可选值："
            "logistic_regression / decision_tree / random_forest / "
            "xgboost / lightgbm / catboost"
        ),
    )

    task_type = Column(
        String(50),
        nullable=False,
        comment=(
            "任务类型，可选值："
            "classification / scoring"
        ),
    )

    framework = Column(
        String(50),
        nullable=False,
        comment=(
            "框架类型，可选值："
            "sklearn / xgboost / lightgbm / catboost"
        ),
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="模型描述",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'inactive'"
        ),
        comment=(
            "模型状态，可选值："
            "active / deprecated / inactive / archived"
        ),
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
        comment="删除时间",
    )

    deleted_by = Column(
        String(50),
        nullable=True,
        comment="删除人",
    )

    deletion_id = Column(
        String(64),
        nullable=True,
        comment="逻辑删除 ID",
    )

    deletion_reason = Column(
        TEXT,
        nullable=True,
        comment="逻辑删除原因",
    )

    restored_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近恢复时间",
    )

    restored_by = Column(
        String(50),
        nullable=True,
        comment="最近恢复人",
    )

    archived_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="归档时间",
    )

    archived_by = Column(
        String(50),
        nullable=True,
        comment="归档人",
    )

    def __repr__(
            self,
    ) -> str:
        """返回模型元数据字符串表示."""
        return (
            f"<Metadata("
            f"model_id='{self.model_id}', "
            f"name='{self.name}', "
            f"model_type='{self.model_type}', "
            f"status='{self.status}'"
            f")>"
        )
