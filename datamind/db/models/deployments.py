# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在不同环境中的部署信息，用于生成部署实例。

核心功能：
  - Deployment: 模型部署记录

使用示例：
  from datamind.db.models.deployments import Deployment

  deployment = Deployment(
      deployment_id="dep_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      framework="sklearn",
      environment="production",
      rollout_type="full",
      role="champion",
      deployed_by="admin",
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


class Deployment(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型部署表"""

    __tablename__ = "deployments"

    __table_args__ = (
        Index(
            "idx_deployments_model_id",
            "model_id",
        ),
        Index(
            "idx_deployments_framework",
            "framework",
        ),
        Index(
            "idx_deployments_model_id_version_id",
            "model_id",
            "version_id",
        ),
        Index(
            "idx_deployments_model_id_environment_status",
            "model_id",
            "environment",
            "status",
        ),
        Index(
            "idx_deployments_effective_time",
            "model_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "uk_deployments_deployment_id",
            "deployment_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "environment IN ("
                "'production', "
                "'staging', "
                "'development', "
                "'testing'"
                ")"
            ),
            name="environment_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="status_valid",
        ),
        CheckConstraint(
            (
                "rollout_type IN ("
                "'full', "
                "'canary', "
                "'shadow'"
                ")"
            ),
            name="rollout_type_valid",
        ),
        CheckConstraint(
            (
                "role IN ("
                "'champion', "
                "'challenger', "
                "'shadow'"
                ")"
            ),
            name="role_valid",
        ),
        CheckConstraint(
            (
                "effective_to IS NULL "
                "OR effective_from IS NULL "
                "OR effective_to > effective_from"
            ),
            name="effective_time_valid",
        ),
        CheckConstraint(
            (
                "config IS NULL "
                "OR jsonb_typeof(config) = 'object'"
            ),
            name="config_object",
        ),
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID，部署实例的唯一标识",
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

    environment = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'production'"
        ),
        comment=(
            "部署环境，可选值："
            "production / staging / development / testing"
        ),
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'inactive'"
        ),
        comment="部署状态，可选值：active / inactive",
    )

    rollout_type = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'full'"
        ),
        comment=(
            "发布类型，可选值："
            "full / canary / shadow"
        ),
    )

    role = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'champion'"
        ),
        comment=(
            "部署角色，可选值："
            "champion / challenger / shadow"
        ),
    )

    effective_from = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="生效开始时间",
    )

    effective_to = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="生效结束时间",
    )

    config = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment="运行时配置，JSON 对象",
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="部署说明",
    )

    deployed_by = Column(
        String(50),
        nullable=True,
        comment="部署人",
    )

    updated_by = Column(
        String(50),
        nullable=True,
        comment="更新人",
    )

    def __repr__(
            self,
    ) -> str:
        """返回部署记录字符串表示"""
        return (
            f"<Deployment("
            f"deployment_id='{self.deployment_id}', "
            f"model_id='{self.model_id}', "
            f"version_id='{self.version_id}', "
            f"environment='{self.environment}', "
            f"role='{self.role}', "
            f"status='{self.status}'"
            f")>"
        )
