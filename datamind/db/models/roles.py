"""角色表.

记录角色及其权限配置，
用于基于角色的访问控制。

核心功能：
  - Role: 角色记录

使用示例：
  from datamind.db.models.roles import Role

  role = Role(
      role_id="rol_0123456789abcdef",
      name="admin",
      description="系统管理员",
      permissions=[
          "model.*",
          "deploy.*",
          "experiment.*",
          "user.*",
      ],
      status="active",
      created_by="usr_0123456789abcdef",
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


class Role(
    IdMixin,
    TimestampMixin,
    Base,
):
    """角色表."""

    __tablename__ = "roles"

    __table_args__ = (
        Index(
            "idx_roles_status",
            "status",
        ),
        Index(
            "idx_roles_created_at",
            "created_at",
        ),
        Index(
            "idx_roles_deleted_at",
            "deleted_at",
        ),
        Index(
            "uk_roles_role_id",
            "role_id",
            unique=True,
        ),
        Index(
            "uk_roles_name",
            "name",
            unique=True,
        ),
        CheckConstraint(
            "btrim(name) <> ''",
            name="name_not_blank",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'inactive'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "permissions IS NULL "
                "OR jsonb_typeof(permissions) = 'array'"
            ),
            name="permissions_array",
        ),
    )

    role_id = Column(
        String(64),
        nullable=False,
        comment="角色 ID，角色的唯一标识",
    )

    name = Column(
        String(64),
        nullable=False,
        comment="角色名称",
    )

    description = Column(
        TEXT,
        nullable=True,
        comment="角色说明",
    )

    permissions = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=True,
        comment=(
            "权限标识列表，JSON 数组。"
            "权限格式为 resource.operation"
        ),
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment=(
            "角色状态，可选值："
            "active / inactive"
        ),
    )

    created_by = Column(
        String(64),
        nullable=True,
        comment="创建用户 ID",
    )

    updated_by = Column(
        String(64),
        nullable=True,
        comment="更新用户 ID",
    )

    deleted_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="逻辑删除时间",
    )

    deleted_by = Column(
        String(64),
        nullable=True,
        comment="逻辑删除操作人",
    )

    deletion_reason = Column(
        TEXT,
        nullable=True,
        comment="逻辑删除原因",
    )

    def __repr__(
            self,
    ) -> str:
        """返回角色字符串表示."""
        return (
            f"<Role("
            f"role_id='{self.role_id}', "
            f"name='{self.name}', "
            f"status='{self.status}'"
            f")>"
        )
