# datamind/db/models/runtimes.py

"""模型运行表

记录部署在统一模型运行时中的加载状态，
用于区分部署配置状态和真实运行状态。
"""

from sqlalchemy.sql import func
from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import TEXT, JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Runtime(Base, IdMixin, TimestampMixin):
    """模型运行表"""

    __tablename__ = "runtimes"

    __table_args__ = (
        Index("idx_runtimes_deployment_id", "deployment_id"),
        Index("idx_runtimes_model_id", "model_id"),
        Index("idx_runtimes_version_id", "version_id"),
        Index("idx_runtimes_framework", "framework"),
        Index("idx_runtimes_status", "status"),
        Index("idx_runtimes_worker_id", "worker_id"),
        Index("idx_runtimes_loaded_at", "loaded_at"),
        Index("idx_runtimes_last_heartbeat_at", "last_heartbeat_at"),
        Index("uk_runtimes_runtime_id", "runtime_id", unique=True),
        Index("uk_runtimes_deployment_worker", "deployment_id", "worker_id", unique=True),
    )

    runtime_id = Column(
        String(64),
        nullable=False,
        comment="运行 ID，运行记录的唯一标识"
    )
    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID"
    )
    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID"
    )
    version_id = Column(
        String(64),
        nullable=False,
        comment="版本 ID"
    )
    framework = Column(
        String(50),
        nullable=False,
        comment="框架类型，可选值 sklearn / xgboost / lightgbm / catboost"
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=text("'unloaded'"),
        comment="运行状态，可选值：loading / loaded / unloaded / failed"
    )
    worker_id = Column(
        String(64),
        nullable=False,
        server_default=text("'default'"),
        comment="运行 Worker 标识，单机模式默认 default"
    )
    loaded_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="加载时间"
    )
    unloaded_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="卸载时间"
    )
    started_by = Column(
        String(50),
        nullable=True,
        comment="加载操作人"
    )
    stopped_by = Column(
        String(50),
        nullable=True,
        comment="卸载操作人"
    )
    last_heartbeat_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后心跳时间"
    )
    error = Column(
        TEXT,
        nullable=True,
        comment="运行错误信息"
    )
    context = Column(
        JSONB,
        nullable=True,
        comment="运行上下文，JSON 格式。可记录模型路径、加载耗时、运行参数等信息"
    )

    def __repr__(self):
        return (
            f"<Runtime("
            f"runtime_id='{self.runtime_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"status='{self.status}'"
            f")>"
        )