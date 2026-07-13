# datamind/db/models/grants.py

"""角色授予表

记录用户与角色之间的授予关系，
用于维护用户角色和权限状态。

核心功能：
  - Grant: 角色授予记录

使用示例：
  from datamind.db.models.grants import Grant

  grant = Grant(
      grant_id="grt_0123456789abcdef",
      user_id="usr_0123456789abcdef",
      role_id="rol_0123456789abcdef",
      status="active",
      granted_by="usr_fedcba9876543210",
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
from sqlalchemy.sql import func

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Grant(
    IdMixin,
    TimestampMixin,
    Base,
):
    """角色授予表"""

    __tablename__ = "grants"

    __table_args__ = (
        Index(
            "idx_grants_user_id",
            "user_id",
        ),
        Index(
            "idx_grants_role_id",
            "role_id",
        ),
        Index(
            "idx_grants_status",
            "status",
        ),
        Index(
            "idx_grants_granted_at",
            "granted_at",
        ),
        Index(
            "idx_grants_user_status",
            "user_id",
            "status",
        ),
        Index(
            "idx_grants_role_status",
            "role_id",
            "status",
        ),
        Index(
            "uk_grants_grant_id",
            "grant_id",
            unique=True,
        ),
        Index(
            "uk_grants_user_role",
            "user_id",
            "role_id",
            unique=True,
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'revoked'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            "btrim(user_id) <> ''",
            name="user_id_not_blank",
        ),
        CheckConstraint(
            "btrim(role_id) <> ''",
            name="role_id_not_blank",
        ),
        CheckConstraint(
            (
                "granted_by IS NULL "
                "OR btrim(granted_by) <> ''"
            ),
            name="granted_by_not_blank",
        ),
        CheckConstraint(
            (
                "revoked_by IS NULL "
                "OR btrim(revoked_by) <> ''"
            ),
            name="revoked_by_not_blank",
        ),
        CheckConstraint(
            (
                "(status = 'active' "
                "AND revoked_at IS NULL) "
                "OR "
                "(status = 'revoked' "
                "AND revoked_at IS NOT NULL)"
            ),
            name="revocation_state_valid",
        ),
    )

    grant_id = Column(
        String(64),
        nullable=False,
        comment="授予 ID，角色授予记录的唯一标识",
    )

    user_id = Column(
        String(64),
        nullable=False,
        comment="用户 ID",
    )

    role_id = Column(
        String(64),
        nullable=False,
        comment="角色 ID",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment=(
            "授予状态，可选值："
            "active / revoked"
        ),
    )

    granted_by = Column(
        String(64),
        nullable=True,
        comment="授予用户 ID",
    )

    granted_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        server_default=func.now(),
        comment="授予时间",
    )

    revoked_by = Column(
        String(64),
        nullable=True,
        comment="撤销用户 ID",
    )

    revoked_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="撤销时间",
    )

    def __repr__(
            self,
    ) -> str:
        """返回角色授予字符串表示"""
        return (
            f"<Grant("
            f"grant_id='{self.grant_id}', "
            f"user_id='{self.user_id}', "
            f"role_id='{self.role_id}', "
            f"status='{self.status}'"
            f")>"
        )
