"""认证令牌仓储

提供刷新令牌的查询、创建、使用记录和撤销能力。

核心功能：
  - get_token: 获取单个刷新令牌记录
  - list_tokens: 获取刷新令牌列表
  - list_active_tokens: 获取有效刷新令牌列表
  - create_token: 创建刷新令牌记录
  - record_token_use: 记录刷新令牌使用时间
  - revoke_token: 撤销单个刷新令牌
  - revoke_user_tokens: 撤销用户的全部刷新令牌

使用示例：
  from datamind.auth.enums import TokenStatus
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.token import TokenRepository

  async with UnitOfWork() as uow:
      repo = TokenRepository(uow.session)

      token = repo.create_token(
          token_id="tok_0123456789abcdef",
          user_id="usr_0123456789abcdef",
          token_hash=(
              "0123456789abcdef"
              "0123456789abcdef"
              "0123456789abcdef"
              "0123456789abcdef"
          ),
          expires_at=expires_at,
          status=TokenStatus.ACTIVE,
          ip="192.168.1.100",
          hostname="client",
          user_agent=(
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0.0.0 Safari/537.36"
          ),
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.auth.enums import TokenStatus
from datamind.db.models.tokens import Token
from datamind.db.repositories.base import BaseRepository


class TokenRepository(BaseRepository):
    """认证令牌仓储"""

    async def get_token(
            self,
            *,
            token_id: str | None = None,
            token_hash: str | None = None,
            for_update: bool = False,
    ) -> Token | None:
        """获取单个刷新令牌记录

        参数：
            token_id: 令牌 ID（可选）
            token_hash: 刷新令牌哈希（可选）
            for_update: 是否锁定记录直到当前事务结束

        返回：
            令牌对象，不存在时返回 None

        异常：
            ValueError: 未提供查询条件或同时提供多个查询条件
        """
        conditions = [
            value is not None
            for value in (
                token_id,
                token_hash,
            )
        ]

        if sum(conditions) != 1:
            raise ValueError(
                "token_id、token_hash 必须且只能提供一个"
            )

        stmt = select(
            Token
        )

        if token_id is not None:
            stmt = stmt.where(
                Token.token_id == token_id
            )
        else:
            stmt = stmt.where(
                Token.token_hash == token_hash
            )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_tokens(
            self,
            *,
            user_id: str | None = None,
            status: TokenStatus | None = None,
            expires_before: datetime | None = None,
            expires_after: datetime | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Token]:
        """获取刷新令牌列表

        参数：
            user_id: 用户 ID（可选）
            status: 令牌状态（可选）
            expires_before: 过期时间上限（可选）
            expires_after: 过期时间下限（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            刷新令牌列表，按创建时间倒序排列
        """
        stmt = select(
            Token
        )

        if user_id is not None:
            stmt = stmt.where(
                Token.user_id == user_id
            )

        if status is not None:
            stmt = stmt.where(
                Token.status == str(
                    status
                )
            )

        if expires_before is not None:
            stmt = stmt.where(
                Token.expires_at <= expires_before
            )

        if expires_after is not None:
            stmt = stmt.where(
                Token.expires_at > expires_after
            )

        stmt = stmt.order_by(
            Token.created_at.desc()
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def list_active_tokens(
            self,
            *,
            user_id: str | None = None,
            current_time: datetime | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Token]:
        """获取有效刷新令牌列表

        参数：
            user_id: 用户 ID（可选）
            current_time: 当前时间（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            状态为 active 且尚未过期的刷新令牌列表
        """
        now = (
            current_time
            or datetime.now(
                timezone.utc
            )
        )

        return await self.list_tokens(
            user_id=user_id,
            status=TokenStatus.ACTIVE,
            expires_after=now,
            limit=limit,
            offset=offset,
        )

    def create_token(
            self,
            *,
            token_id: str,
            user_id: str,
            token_hash: str,
            expires_at: datetime,
            status: TokenStatus = TokenStatus.ACTIVE,
            ip: str | None = None,
            hostname: str | None = None,
            user_agent: str | None = None,
    ) -> Token:
        """创建刷新令牌记录

        参数：
            token_id: 令牌 ID
            user_id: 用户 ID
            token_hash: 刷新令牌哈希
            expires_at: 令牌过期时间
            status: 令牌状态
            ip: 登录客户端 IP 地址（可选）
            hostname: 登录客户端主机名称（可选）
            user_agent: 登录客户端 User-Agent（可选）

        返回：
            创建后的令牌对象
        """
        new_token = Token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            status=str(
                status
            ),
            expires_at=expires_at,
        )

        if ip is not None:
            new_token.ip = ip

        if hostname is not None:
            new_token.hostname = hostname

        if user_agent is not None:
            new_token.user_agent = user_agent

        self.add(
            new_token
        )

        return new_token

    def record_token_use(
            self,
            token: Token,
            *,
            used_at: datetime | None = None,
    ) -> Token:
        """记录刷新令牌使用时间

        参数：
            token: 令牌对象
            used_at: 使用时间（可选）

        返回：
            更新后的令牌对象
        """
        token.last_used_at = (
            used_at
            or datetime.now(
                timezone.utc
            )
        )

        return token

    def revoke_token(
            self,
            token: Token,
            *,
            revoked_by: str | None = None,
            revoke_reason: str | None = None,
            revoked_at: datetime | None = None,
    ) -> Token:
        """撤销单个刷新令牌

        参数：
            token: 令牌对象
            revoked_by: 撤销用户 ID（可选）
            revoke_reason: 撤销原因（可选）
            revoked_at: 撤销时间（可选）

        返回：
            撤销后的令牌对象
        """
        if token.status == str(
                TokenStatus.REVOKED
        ):
            return token

        token.status = str(
            TokenStatus.REVOKED
        )
        token.revoked_by = revoked_by
        token.revoke_reason = revoke_reason
        token.revoked_at = (
            revoked_at
            or datetime.now(
                timezone.utc
            )
        )

        return token

    async def revoke_user_tokens(
            self,
            *,
            user_id: str,
            revoked_by: str | None = None,
            revoke_reason: str | None = None,
            revoked_at: datetime | None = None,
    ) -> list[Token]:
        """撤销用户的全部刷新令牌

        参数：
            user_id: 用户 ID
            revoked_by: 撤销用户 ID（可选）
            revoke_reason: 撤销原因（可选）
            revoked_at: 撤销时间（可选）

        返回：
            已撤销的令牌列表
        """
        tokens = await self.list_tokens(
            user_id=user_id,
            status=TokenStatus.ACTIVE,
            limit=None,
        )

        timestamp = (
            revoked_at
            or datetime.now(
                timezone.utc
            )
        )

        for token in tokens:
            self.revoke_token(
                token,
                revoked_by=revoked_by,
                revoke_reason=revoke_reason,
                revoked_at=timestamp,
            )

        return tokens
