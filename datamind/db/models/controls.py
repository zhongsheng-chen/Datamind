"""模型运行控制表

记录模型部署的期望运行状态和控制版本，
用于协调多个 Worker 的模型加载、卸载和重新加载。

核心功能：
  - Control: 模型运行控制记录

使用示例：
  from datamind.db.models.controls import Control

  control = Control(
      control_id="ctl_0123456789abcdef",
      deployment_id="dep_0123456789abcdef",
      environment="production",
      desired_status="unloaded",
      generation=1,
      created_by="admin",
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    String,
    text,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Control(
    IdMixin,
    TimestampMixin,
    Base,
):
    """模型运行控制表"""

    __tablename__ = "controls"

    __table_args__ = (
        Index(
            "idx_controls_environment",
            "environment",
        ),
        Index(
            "idx_controls_desired_status",
            "desired_status",
        ),
        Index(
            "idx_controls_environment_desired_status",
            "environment",
            "desired_status",
        ),
        Index(
            "idx_controls_updated_at",
            "updated_at",
        ),
        Index(
            "uk_controls_control_id",
            "control_id",
            unique=True,
        ),
        Index(
            "uk_controls_deployment_id",
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
            "desired_status IN ('loaded', 'unloaded')",
            name="desired_status_valid",
        ),
        CheckConstraint(
            "generation >= 1",
            name="generation_positive",
        ),
    )

    control_id = Column(
        String(64),
        nullable=False,
        comment="控制 ID，运行控制记录的唯一标识",
    )

    deployment_id = Column(
        String(64),
        nullable=False,
        comment="部署 ID，每个部署仅对应一条运行控制记录",
    )

    environment = Column(
        String(32),
        nullable=False,
        server_default=text(
            "'production'"
        ),
        comment=(
            "运行环境，可选值："
            "production / staging / development / testing"
        ),
    )

    desired_status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'unloaded'"
        ),
        comment="期望运行状态，可选值：loaded / unloaded",
    )

    generation = Column(
        Integer,
        nullable=False,
        server_default=text(
            "1"
        ),
        comment="控制版本号，每次状态变更或重新加载时递增",
    )

    created_by = Column(
        String(50),
        nullable=True,
        comment="创建人",
    )

    updated_by = Column(
        String(50),
        nullable=True,
        comment="最近更新人",
    )

    def __repr__(
            self,
    ) -> str:
        """返回模型运行控制字符串表示"""
        return (
            f"<Control("
            f"control_id='{self.control_id}', "
            f"deployment_id='{self.deployment_id}', "
            f"environment='{self.environment}', "
            f"desired_status='{self.desired_status}', "
            f"generation={self.generation}"
            f")>"
        )
