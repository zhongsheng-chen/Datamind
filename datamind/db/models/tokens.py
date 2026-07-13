# datamind/db/models/tokens.py

"""认证令牌表

记录刷新令牌哈希及其有效期和撤销状态，
用于登录会话续期、退出登录和令牌失效控制。

核心功能：
  - Token: 刷新令牌记录

使用示例：
  from datamind.db.models.tokens import Token

  token = Token(
      token_id="tok_0123456789abcdef",
      user_id="usr_0123456789abcdef",
      token_hash=(
          "0123456789abcdef"
          "0123456789abcdef"
          "0123456789abcdef"
          "0123456789abcdef"
      ),
      status="active",
      ip="192.168.1.100",
      hostname="client",
      user_agent=(
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0.0.0 Safari/537.36"
      ),
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


class Token(
    IdMixin,
    TimestampMixin,
    Base,
):
    """认证令牌表"""

    __tablename__ = "tokens"

    __table_args__ = (
        Index(
            "idx_tokens_user_id",
            "user_id",
        ),
        Index(
            "idx_tokens_status",
            "status",
        ),
        Index(
            "idx_tokens_expires_at",
            "expires_at",
        ),
        Index(
            "idx_tokens_last_used_at",
            "last_used_at",
        ),
        Index(
            "idx_tokens_user_status",
            "user_id",
            "status",
        ),
        Index(
            "uk_tokens_token_id",
            "token_id",
            unique=True,
        ),
        Index(
            "uk_tokens_token_hash",
            "token_hash",
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
            "btrim(token_hash) <> ''",
            name="token_hash_not_blank",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="expires_at_after_created_at",
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
        CheckConstraint(
            (
                "revoked_by IS NULL "
                "OR btrim(revoked_by) <> ''"
            ),
            name="revoked_by_not_blank",
        ),
    )

    token_id = Column(
        String(64),
        nullable=False,
        comment="令牌 ID，刷新令牌记录的唯一标识",
    )

    user_id = Column(
        String(64),
        nullable=False,
        comment="用户 ID",
    )

    token_hash = Column(
        String(128),
        nullable=False,
        comment="刷新令牌哈希",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text(
            "'active'"
        ),
        comment=(
            "令牌状态，可选值："
            "active / revoked"
        ),
    )

    expires_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        comment="令牌过期时间",
    )

    last_used_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="最近使用时间",
    )

    revoked_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="撤销时间",
    )

    revoked_by = Column(
        String(64),
        nullable=True,
        comment="撤销用户 ID",
    )

    revoke_reason = Column(
        TEXT,
        nullable=True,
        comment="撤销原因",
    )

    ip = Column(
        String(64),
        nullable=True,
        comment="登录客户端 IP 地址",
    )

    hostname = Column(
        String(128),
        nullable=True,
        comment="登录客户端主机名称",
    )

    user_agent = Column(
        TEXT,
        nullable=True,
        comment="登录客户端 User-Agent",
    )

    def __repr__(
            self,
    ) -> str:
        """返回认证令牌字符串表示"""
        return (
            f"<Token("
            f"token_id='{self.token_id}', "
            f"user_id='{self.user_id}', "
            f"status='{self.status}', "
            f"expires_at='{self.expires_at}'"
            f")>"
        )
