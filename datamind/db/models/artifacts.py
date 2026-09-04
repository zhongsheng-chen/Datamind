# datamind/db/models/artifacts.py

"""模型制品表

记录模型版本的制品修订信息，包括存储位置、
完整性摘要、生命周期状态和永久清理结果。

核心功能：
  - Artifact: 模型制品修订记录

使用示例：
  from datamind.db.models.artifacts import Artifact

  artifact = Artifact(
      artifact_id="art_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      revision=1,
      sha256="4f7c2a8d...c91e",
      digest="9b3e1f6a...72d4",
      source_path="models/scorecard.pkl",
      model_key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/scorecard.pkl"
      ),
      bento_tag="scorecard:abcdefgh",
      status="active",
      created_by="admin",
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
from sqlalchemy.dialects.postgresql import TEXT

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Artifact(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型制品修订表"""

    __tablename__ = "artifacts"

    __table_args__ = (
        Index(
            "idx_artifacts_version_id",
            "version_id",
        ),
        Index(
            "idx_artifacts_status",
            "status",
        ),
        Index(
            "uk_artifacts_artifact_id",
            "artifact_id",
            unique=True,
        ),
        Index(
            "uk_artifacts_version_revision",
            "version_id",
            "revision",
            unique=True,
        ),
        Index(
            "uk_artifacts_model_key",
            "model_key",
            unique=True,
        ),
        Index(
            "uk_artifacts_bento_tag",
            "bento_tag",
            unique=True,
        ),
        Index(
            "uk_artifacts_active_version",
            "version_id",
            unique=True,
            postgresql_where=text(
                "status = 'active'"
            ),
        ),
        CheckConstraint(
            "revision >= 1",
            name="revision_positive",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'retired', "
                "'purge_pending', "
                "'purged', "
                "'purge_failed'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            "purge_attempts >= 0",
            name="purge_attempts_non_negative",
        ),
    )

    artifact_id = Column(
        String(64),
        nullable=False,
        comment="制品 ID",
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="模型版本 ID",
    )

    revision = Column(
        Integer,
        nullable=False,
        comment="修订号",
    )

    sha256 = Column(
        String(64),
        nullable=True,
        comment="模型文件 SHA-256",
    )

    digest = Column(
        String(64),
        nullable=True,
        comment="模型摘要",
    )

    source_path = Column(
        String(255),
        nullable=False,
        comment="模型文件原始路径",
    )

    model_key = Column(
        String(255),
        nullable=False,
        comment="模型文件存储键",
    )

    bento_tag = Column(
        String(100),
        nullable=False,
        comment="BentoML 模型标签",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment="制品状态",
    )

    created_by = Column(
        String(50),
        nullable=True,
        comment="创建人",
    )

    retired_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="停止使用时间",
    )

    retired_by = Column(
        String(50),
        nullable=True,
        comment="停止使用操作人",
    )

    purge_requested_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="制品清理请求时间",
    )

    purge_requested_by = Column(
        String(50),
        nullable=True,
        comment="制品清理请求人",
    )

    purge_reason = Column(
        TEXT,
        nullable=True,
        comment="制品永久清理原因",
    )

    purged_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="制品清理完成时间",
    )

    purged_by = Column(
        String(50),
        nullable=True,
        comment="制品清理完成人",
    )

    purge_attempts = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="制品清理尝试次数",
    )

    purge_error = Column(
        TEXT,
        nullable=True,
        comment="最近一次制品清理错误",
    )

    def __repr__(self) -> str:
        """返回模型制品字符串表示"""
        return (
            "<Artifact("
            f"artifact_id='{self.artifact_id}', "
            f"version_id='{self.version_id}', "
            f"revision={self.revision}, "
            f"status='{self.status}'"
            ")>"
        )
