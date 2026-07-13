# datamind/db/models/versions.py

"""模型版本表

存储模型版本信息，包括模型产物、输入输出 Schema、
模型参数、评估指标、运行框架和生命周期状态。

核心功能：
  - Version: 模型版本记录

使用示例：
  from datamind.db.models.versions import Version

  version = Version(
      version_id="ver_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      version="1.0.0",
      framework="sklearn",
      bento_tag="scorecard:abcdefgh",
      model_path=(
          "s3://datamind/models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/scorecard.pkl"
      ),
      model_key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/scorecard.pkl"
      ),
      current_artifact_id="art_0123456789abcdef",
      artifact_sha256="4f7c2a8d...c91e",
      artifact_digest="9b3e1f6a...72d4",
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
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Version(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型版本表"""

    __tablename__ = "versions"

    __table_args__ = (
        Index(
            "idx_versions_model_id",
            "model_id",
        ),
        Index(
            "idx_versions_framework",
            "framework",
        ),
        Index(
            "idx_versions_status",
            "status",
        ),
        Index(
            "idx_versions_created_at",
            "created_at",
        ),
        Index(
            "uk_versions_model_id_version",
            "model_id",
            "version",
            unique=True,
        ),
        Index(
            "uk_versions_version_id",
            "version_id",
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
                "'active', "
                "'inactive', "
                "'deprecated', "
                "'archived'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "input_schema IS NULL "
                "OR jsonb_typeof(input_schema) = 'object'"
            ),
            name="input_schema_object",
        ),
        CheckConstraint(
            (
                "output_schema IS NULL "
                "OR jsonb_typeof(output_schema) = 'object'"
            ),
            name="output_schema_object",
        ),
        CheckConstraint(
            (
                "params IS NULL "
                "OR jsonb_typeof(params) = 'object'"
            ),
            name="params_object",
        ),
        CheckConstraint(
            (
                "metrics IS NULL "
                "OR jsonb_typeof(metrics) = 'object'"
            ),
            name="metrics_object",
        ),
        CheckConstraint(
            "artifact_revision >= 1",
            name="artifact_revision_positive",
        ),
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="版本 ID，模型版本的唯一标识",
    )

    model_id = Column(
        String(64),
        nullable=False,
        comment="模型 ID",
    )

    version = Column(
        String(50),
        nullable=False,
        comment="版本号",
    )

    framework = Column(
        String(50),
        nullable=False,
        comment=(
            "框架类型，可选值："
            "sklearn / xgboost / lightgbm / catboost"
        ),
    )

    input_schema = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="输入 Schema，JSON 对象",
    )

    output_schema = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="输出 Schema，JSON 对象",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'inactive'"
        ),
        comment=(
            "版本状态，可选值："
            "active / inactive / deprecated / archived"
        ),
    )

    current_artifact_id = Column(
        String(64),
        nullable=False,
        comment="当前生效制品 ID",
    )

    artifact_revision = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="当前制品修订号",
    )

    artifact_sha256 = Column(
        String(64),
        nullable=True,
        comment="当前模型文件 SHA-256",
    )

    artifact_digest = Column(
        String(64),
        nullable=True,
        comment="当前模型与 Schema 组合摘要",
    )

    bento_tag = Column(
        String(100),
        nullable=False,
        comment=(
            "BentoML 标签，由模型名称和 BentoML 版本组成，"
            "格式为 模型名:版本"
        ),
    )

    model_path = Column(
        String(255),
        nullable=False,
        comment="模型文件原始路径",
    )

    model_key = Column(
        String(255),
        nullable=False,
        comment="模型文件存储键",
    )

    input_schema_key = Column(
        String(255),
        nullable=True,
        comment="输入 Schema 文件存储键",
    )

    output_schema_key = Column(
        String(255),
        nullable=True,
        comment="输出 Schema 文件存储键",
    )

    params = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="模型参数，JSON 对象",
    )

    metrics = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="模型评估指标，JSON 对象",
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="版本说明",
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
        """返回模型版本字符串表示"""
        return (
            f"<Version("
            f"version_id='{self.version_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}', "
            f"framework='{self.framework}', "
            f"status='{self.status}'"
            f")>"
        )
