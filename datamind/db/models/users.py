# datamind/db/models/users.py

"""用户表

记录用户身份、密码和登录状态，用于用户认证和权限控制。

核心功能：
  - User: 用户记录

使用示例：
  from datamind.db.models.users import User

  user = User(
      user_id="usr_0123456789abcdef",
      username="admin",
      password_hash="$argon2id$...",
      display_name="系统管理员",
      email="admin@example.com",
      status="active",
      created_by="usr_fedcba9876543210",
  )
"""

from sqlalchemy import (
    Boolean,
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


class User(
    IdMixin,
    TimestampMixin,
    Base,
):
    """用户表"""

    __tablename__ = "users"

    __table_args__ = (
        Index(
            "idx_users_status",
            "status",
        ),
        Index(
            "idx_users_created_at",
            "created_at",
        ),
        Index(
            "idx_users_deleted_at",
            "deleted_at",
        ),
        Index(
            "uk_users_user_id",
            "user_id",
            unique=True,
        ),
        Index(
            "uk_users_username",
            "username",
            unique=True,
        ),
        Index(
            "uk_users_email",
            "email",
            unique=True,
            postgresql_where=text(
                "email IS NOT NULL"
            ),
        ),
        CheckConstraint(
            (
                "status IN ("
                "'active', "
                "'disabled', "
                "'locked'"
                ")"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            "failed_login_count >= 0",
            name="failed_login_count_non_negative",
        ),
        CheckConstraint(
            "btrim(username) <> ''",
            name="username_not_blank",
        ),
        CheckConstraint(
            (
                "btrim(password_hash) <> ''"
            ),
            name="password_hash_not_blank",
        ),
        CheckConstraint(
            (
                "email IS NULL "
                "OR btrim(email) <> ''"
            ),
            name="email_not_blank",
        ),
    )

    user_id = Column(
        String(64),
        nullable=False,
        comment="用户 ID，用户的唯一标识",
    )

    username = Column(
        String(64),
        nullable=False,
        comment="登录用户名",
    )

    password_hash = Column(
        String(512),
        nullable=False,
        comment="密码哈希",
    )

    display_name = Column(
        String(128),
        nullable=True,
        comment="用户显示名称",
    )

    email = Column(
        String(254),
        nullable=True,
        comment="用户邮箱",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment=(
            "用户状态，可选值："
            "active / disabled / locked"
        ),
    )

    is_break_glass = Column(
        Boolean,
        nullable=False,
        server_default=text(
            "false"
        ),
        comment="是否为本地应急账户",
    )

    failed_login_count = Column(
        Integer,
        nullable=False,
        server_default=text(
            "0"
        ),
        comment="连续登录失败次数",
    )

    locked_until = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="临时锁定截止时间",
    )

    last_login_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="最近登录时间",
    )

    password_changed_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="最近密码修改时间",
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
        """返回用户字符串表示"""
        return (
            f"<User("
            f"user_id='{self.user_id}', "
            f"username='{self.username}', "
            f"status='{self.status}', "
            f"is_break_glass={self.is_break_glass}"
            f")>"
        )
