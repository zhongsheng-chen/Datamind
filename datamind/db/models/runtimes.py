"""模型运行表.

记录部署在各 Worker 中的实际运行状态，
用于区分部署配置状态和模型真实加载状态。

核心功能：
  - Runtime: Worker 模型运行记录

使用示例：
  from datamind.db.models.runtimes import Runtime

  runtime = Runtime(
      runtime_id="rtm_0123456789abcdef",
      deployment_id="dep_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      framework="sklearn",
      status="stopped",
      worker_id="worker-1",
      applied_generation=None,
      context={
          "worker_id": "worker-1",
          ...
      },
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
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


class Runtime(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型运行表."""

    __tablename__ = "runtimes"

    __table_args__ = (
        Index(
            "idx_runtimes_model_id",
            "model_id",
        ),
        Index(
            "idx_runtimes_version_id",
            "version_id",
        ),
        Index(
            "idx_runtimes_framework",
            "framework",
        ),
        Index(
            "idx_runtimes_status",
            "status",
        ),
        Index(
            "idx_runtimes_worker_id",
            "worker_id",
        ),
        Index(
            "idx_runtimes_loaded_at",
            "loaded_at",
        ),
        Index(
            "idx_runtimes_last_heartbeat_at",
            "last_heartbeat_at",
        ),
        Index(
            "uk_runtimes_runtime_id",
            "runtime_id",
            unique=True,
        ),
        Index(
            "uk_runtimes_deployment_worker",
            "deployment_id",
            "worker_id",
            unique=True,
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
                "'starting', "
                "'running', "
                "'stopping', "
                "'stopped', "
                "'failed'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "applied_generation IS NULL "
                "OR applied_generation >= 1"
            ),
            name="applied_generation_positive",
        ),
        CheckConstraint(
            (
                "context IS NULL "
                "OR jsonb_typeof(context) = 'object'"
            ),
            name="context_object",
        ),
    )

    runtime_id = Column(
        String(64),
        nullable=False,
        comment="运行 ID，运行记录的唯一标识",
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID",
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID",
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="版本 ID",
    )

    framework = Column(
        String(50),
        nullable=False,
        comment=(
            "框架类型，可选值："
            "sklearn / xgboost / lightgbm / catboost"
        ),
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'stopped'"
        ),
        comment=(
            "运行状态，可选值："
            "starting / running / stopping / stopped / failed"
        ),
    )

    worker_id = Column(
        String(64),
        nullable=False,
        server_default=text(
            "'default'"
        ),
        comment="运行 Worker 标识，单机模式默认 default",
    )

    loaded_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="加载时间",
    )

    unloaded_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="卸载时间",
    )

    started_by = Column(
        String(50),
        nullable=True,
        comment="加载操作人",
    )

    stopped_by = Column(
        String(50),
        nullable=True,
        comment="卸载操作人",
    )

    last_heartbeat_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="最后心跳时间",
    )

    applied_generation = Column(
        Integer,
        nullable=True,
        comment="控制版本号，当前 Worker 已应用的控制版本",
    )

    error = Column(
        TEXT,
        nullable=True,
        comment="运行错误信息",
    )

    context = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "运行上下文，JSON 对象，可记录模型路径、"
            "加载耗时和运行参数等信息"
        ),
    )

    def __repr__(
            self,
    ) -> str:
        """返回模型运行记录字符串表示."""
        return (
            f"<Runtime("
            f"runtime_id='{self.runtime_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"worker_id='{self.worker_id}', "
            f"status='{self.status}', "
            f"applied_generation={self.applied_generation}"
            f")>"
        )
