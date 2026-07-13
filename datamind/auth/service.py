# datamind/auth/service.py

"""认证服务

整合本地认证、用户、角色、角色授予和刷新令牌仓储，
提供登录、令牌续期、退出登录和访问令牌认证能力。

核心功能：
  - AuthService.login: 使用本地用户名和密码登录
  - AuthService.refresh: 使用刷新令牌续期并轮换刷新令牌
  - AuthService.logout: 撤销刷新令牌
  - AuthService.authenticate_access_token: 认证访问令牌
  - AuthService.get_authenticated_user: 获取已认证用户信息

使用示例：
  from datamind.auth.schemas import LoginRequest
  from datamind.auth.service import AuthService
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import (
      GrantRepository,
      RoleRepository,
      TokenRepository,
      UserRepository,
  )

  async with UnitOfWork() as uow:
      service = AuthService(
          user_repo=UserRepository(
              uow.session
          ),
          role_repo=RoleRepository(
              uow.session
          ),
          grant_repo=GrantRepository(
              uow.session
          ),
          token_repo=TokenRepository(
              uow.session
          ),
          secret_key="replace-with-a-secure-secret",
      )

      tokens = await service.login(
          LoginRequest(
              username="admin",
              password="P@ssw1rd",
          )
      )
"""

from collections.abc import Iterable
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from ipaddress import ip_address, ip_network

import structlog
from pydantic import ValidationError

from datamind.auth.enums import (
    RoleStatus,
    TokenStatus,
    UserStatus,
)
from datamind.auth.errors import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.providers import (
    BaseAuthProvider,
    LocalAuthProvider,
    LocalProviderConfig,
    PasswordCredentials,
    ProviderIdentity,
)
from datamind.auth.schemas import (
    AccessTokenClaims,
    AuthenticatedUser,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from datamind.auth.token import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_refresh_token,
)
from datamind.db.models.users import User
from datamind.db.repositories import (
    GrantRepository,
    RoleRepository,
    TokenRepository,
    UserRepository,
)
from datamind.utils.generator import generate_random_id


logger = structlog.get_logger(__name__)


class AuthService:
    """认证服务"""

    def __init__(
            self,
            *,
            user_repo: UserRepository,
            role_repo: RoleRepository,
            grant_repo: GrantRepository,
            token_repo: TokenRepository,
            secret_key: str,
            provider: BaseAuthProvider | None = None,
            algorithm: str = "HS256",
            access_token_expires_minutes: int = 30,
            refresh_token_expires_days: int = 7,
            max_failed_login_attempts: int = 5,
            lock_minutes: int = 30,
            local_allowed_networks: Iterable[str] = (),
            break_glass_access_token_expires_minutes: int = 15,
    ) -> None:
        """初始化认证服务

        参数：
            user_repo: 用户仓储
            role_repo: 角色仓储
            grant_repo: 角色授予仓储
            token_repo: 刷新令牌仓储
            secret_key: JWT 签名密钥
            provider: 本地认证提供方（可选）
            algorithm: JWT 签名算法
            access_token_expires_minutes: 访问令牌有效分钟数
            refresh_token_expires_days: 刷新令牌有效天数
            max_failed_login_attempts: 本地认证最大连续失败次数
            lock_minutes: 本地认证达到失败阈值后的锁定分钟数
            local_allowed_networks: LOCAL 认证允许访问的网段
            break_glass_access_token_expires_minutes:
                应急访问令牌有效分钟数

        异常：
            ValueError: 配置参数无效
        """
        normalized_secret_key = secret_key.strip()
        normalized_algorithm = algorithm.strip()

        if normalized_secret_key == "":
            raise ValueError(
                "secret_key 不能为空"
            )

        if normalized_algorithm == "":
            raise ValueError(
                "algorithm 不能为空"
            )

        if access_token_expires_minutes <= 0:
            raise ValueError(
                "access_token_expires_minutes 必须大于 0"
            )

        if refresh_token_expires_days <= 0:
            raise ValueError(
                "refresh_token_expires_days 必须大于 0"
            )

        if max_failed_login_attempts <= 0:
            raise ValueError(
                "max_failed_login_attempts 必须大于 0"
            )

        if lock_minutes <= 0:
            raise ValueError(
                "lock_minutes 必须大于 0"
            )

        if break_glass_access_token_expires_minutes <= 0:
            raise ValueError(
                "break_glass_access_token_expires_minutes "
                "必须大于 0"
            )

        self.user_repo = user_repo
        self.role_repo = role_repo
        self.grant_repo = grant_repo
        self.token_repo = token_repo

        self.secret_key = normalized_secret_key
        self.algorithm = normalized_algorithm
        self.access_token_expires_minutes = (
            access_token_expires_minutes
        )
        self.refresh_token_expires_days = (
            refresh_token_expires_days
        )
        self.local_allowed_networks = tuple(
            ip_network(
                network,
                strict=False,
            )
            for network in local_allowed_networks
        )
        self.break_glass_access_token_expires_minutes = (
            break_glass_access_token_expires_minutes
        )

        self.provider = (
            provider
            or LocalAuthProvider(
                user_repo=user_repo,
                config=LocalProviderConfig(
                    max_failed_login_attempts=(
                        max_failed_login_attempts
                    ),
                    lock_minutes=lock_minutes,
                ),
            )
        )

    async def login(
            self,
            request: LoginRequest,
            *,
            ip: str | None = None,
            hostname: str | None = None,
            user_agent: str | None = None,
            current_time: datetime | None = None,
    ) -> TokenResponse:
        """使用本地用户名和密码登录

        参数：
            request: 登录请求
            ip: 客户端 IP 地址（可选）
            hostname: 客户端主机名称（可选）
            user_agent: 客户端 User-Agent（可选）
            current_time: 当前时间（可选）

        返回：
            访问令牌和刷新令牌
        """
        now = self._normalize_current_time(
            current_time
        )
        self._validate_local_network(
            ip
        )
        identity = await self.provider.authenticate(
            PasswordCredentials(
                username=request.username,
                password=(
                    request.password.get_secret_value()
                ),
            ),
            current_time=now,
        )

        user = await self._resolve_user(
            identity
        )

        self._validate_user_status(
            user,
            current_time=now,
        )

        if bool(
                user.is_break_glass
        ):
            logger.warning(
                "本地应急账户登录成功",
                user_id=user.user_id,
                username=user.username,
                ip=ip,
                hostname=hostname,
            )

        return await self._issue_tokens(
            user,
            current_time=now,
            ip=ip,
            hostname=hostname,
            user_agent=user_agent,
        )

    async def refresh(
            self,
            request: RefreshTokenRequest,
            *,
            ip: str | None = None,
            hostname: str | None = None,
            user_agent: str | None = None,
            current_time: datetime | None = None,
    ) -> TokenResponse:
        """续期并轮换刷新令牌

        参数：
            request: 刷新令牌请求
            ip: 新令牌对应的客户端 IP 地址（可选）
            hostname: 新令牌对应的客户端主机名称（可选）
            user_agent: 新令牌对应的 User-Agent（可选）
            current_time: 当前时间（可选）

        返回：
            新的访问令牌和刷新令牌

        异常：
            InvalidRefreshTokenError: 刷新令牌无效
            RefreshTokenRevokedError: 刷新令牌已撤销
            RefreshTokenExpiredError: 刷新令牌已过期
            UserDisabledError: 用户已停用
            UserLockedError: 用户已锁定
        """
        now = self._normalize_current_time(
            current_time
        )

        refresh_token = (
            request.refresh_token.get_secret_value()
        )
        token_hash = hash_refresh_token(
            refresh_token
        )

        token_record = await self.token_repo.get_token(
            token_hash=token_hash,
            for_update=True,
        )

        if token_record is None:
            raise InvalidRefreshTokenError()

        if not verify_refresh_token(
                refresh_token=refresh_token,
                token_hash=token_record.token_hash,
        ):
            raise InvalidRefreshTokenError()

        if token_record.status == str(
                TokenStatus.REVOKED
        ):
            raise RefreshTokenRevokedError()

        if token_record.status != str(
                TokenStatus.ACTIVE
        ):
            raise InvalidRefreshTokenError()

        if self._to_utc(
                token_record.expires_at
        ) <= now:
            self.token_repo.revoke_token(
                token_record,
                revoked_by=token_record.user_id,
                revoke_reason="refresh_token_expired",
                revoked_at=now,
            )
            raise RefreshTokenExpiredError()

        user = await self.user_repo.get_user(
            user_id=token_record.user_id
        )

        if user is None:
            raise InvalidRefreshTokenError()

        if bool(
                user.is_break_glass
        ):
            self.token_repo.revoke_token(
                token_record,
                revoked_by=user.user_id,
                revoke_reason=(
                    "break_glass_refresh_denied"
                ),
                revoked_at=now,
            )
            raise InvalidRefreshTokenError(
                "应急账户不允许使用刷新令牌"
            )

        self._validate_user_status(
            user,
            current_time=now,
        )

        self.token_repo.record_token_use(
            token_record,
            used_at=now,
        )
        self.token_repo.revoke_token(
            token_record,
            revoked_by=user.user_id,
            revoke_reason="refresh_token_rotated",
            revoked_at=now,
        )

        return await self._issue_tokens(
            user,
            current_time=now,
            ip=(
                ip
                if ip is not None
                else token_record.ip
            ),
            hostname=(
                hostname
                if hostname is not None
                else token_record.hostname
            ),
            user_agent=(
                user_agent
                if user_agent is not None
                else token_record.user_agent
            ),
        )

    async def logout(
            self,
            request: LogoutRequest,
            *,
            revoked_by: str | None = None,
            current_time: datetime | None = None,
    ) -> bool:
        """退出登录并撤销刷新令牌

        参数：
            request: 退出登录请求
            revoked_by: 执行撤销的用户 ID（可选）
            current_time: 当前时间（可选）

        返回：
            True 表示本次撤销了有效令牌；
            False 表示令牌不存在或已经撤销

        说明：
            退出登录保持幂等，重复提交不会抛出异常。
        """
        now = self._normalize_current_time(
            current_time
        )

        refresh_token = (
            request.refresh_token.get_secret_value()
        )
        token_hash = hash_refresh_token(
            refresh_token
        )

        token_record = await self.token_repo.get_token(
            token_hash=token_hash
        )

        if (
                token_record is None
                or token_record.status == str(
                    TokenStatus.REVOKED
                )
        ):
            return False

        self.token_repo.revoke_token(
            token_record,
            revoked_by=(
                revoked_by
                or token_record.user_id
            ),
            revoke_reason="logout",
            revoked_at=now,
        )

        return True

    async def authenticate_access_token(
            self,
            access_token: str,
            *,
            current_time: datetime | None = None,
    ) -> AuthenticatedUser:
        """认证访问令牌

        参数：
            access_token: JWT 访问令牌
            current_time: 当前时间（保留参数，便于测试）

        返回：
            当前已认证用户信息

        异常：
            InvalidAccessTokenError: 访问令牌无效
            UserDisabledError: 用户已停用
            UserLockedError: 用户已锁定
        """
        now = self._normalize_current_time(
            current_time
        )

        payload = decode_access_token(
            token=access_token,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
        )

        if payload is None:
            raise InvalidAccessTokenError()

        try:
            claims = AccessTokenClaims.model_validate(
                payload
            )

        except ValidationError as exc:
            raise InvalidAccessTokenError() from exc

        user = await self.user_repo.get_user(
            user_id=claims.sub
        )

        if user is None:
            raise InvalidAccessTokenError()

        self._validate_user_status(
            user,
            current_time=now,
        )

        return await self._build_authenticated_user(
            user
        )

    async def get_authenticated_user(
            self,
            user_id: str,
            *,
            current_time: datetime | None = None,
    ) -> AuthenticatedUser:
        """获取已认证用户信息

        参数：
            user_id: 用户 ID
            current_time: 当前时间（可选）

        返回：
            已认证用户信息

        异常：
            InvalidAccessTokenError: 用户不存在
            UserDisabledError: 用户已停用
            UserLockedError: 用户已锁定
        """
        now = self._normalize_current_time(
            current_time
        )

        user = await self.user_repo.get_user(
            user_id=user_id
        )

        if user is None:
            raise InvalidAccessTokenError()

        self._validate_user_status(
            user,
            current_time=now,
        )

        return await self._build_authenticated_user(
            user
        )

    async def _resolve_user(
            self,
            identity: ProviderIdentity,
    ) -> User:
        """根据认证身份匹配本地用户"""
        user = await self.user_repo.get_user(
            username=identity.username
        )

        if (
                user is None
                and identity.email is not None
        ):
            user = await self.user_repo.get_user(
                email=identity.email
            )

        if user is None:
            raise InvalidCredentialsError(
                "认证成功，但未找到对应的本地用户"
            )

        return user

    async def _issue_tokens(
            self,
            user: User,
            *,
            current_time: datetime,
            ip: str | None,
            hostname: str | None,
            user_agent: str | None,
    ) -> TokenResponse:
        """签发访问令牌和刷新令牌"""
        roles, permissions = (
            await self._load_roles_and_permissions(
                user.user_id
            )
        )

        is_break_glass = bool(
            user.is_break_glass
        )
        access_token_expires_minutes = (
            self.break_glass_access_token_expires_minutes
            if is_break_glass
            else self.access_token_expires_minutes
        )

        access_token = create_access_token(
            user_id=user.user_id,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            expires_minutes=access_token_expires_minutes,
            issued_at=current_time,
            extra_claims={
                "username": user.username,
                "roles": roles,
                "permissions": permissions,
            },
        )

        if is_break_glass:
            return TokenResponse(
                access_token=access_token,
                refresh_token=None,
                expires_in=(
                    access_token_expires_minutes
                    * 60
                ),
            )

        refresh_token = generate_refresh_token()
        refresh_token_hash = hash_refresh_token(
            refresh_token
        )
        refresh_expires_at = (
            current_time
            + timedelta(
                days=(
                    self.refresh_token_expires_days
                )
            )
        )

        self.token_repo.create_token(
            token_id=generate_random_id(
                prefix="tok"
            ),
            user_id=user.user_id,
            token_hash=refresh_token_hash,
            expires_at=refresh_expires_at,
            ip=ip,
            hostname=hostname,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=(
                access_token_expires_minutes
                * 60
            ),
        )

    def _validate_local_network(
            self,
            ip: str | None,
    ) -> None:
        """校验 LOCAL 认证来源网段"""
        if not self.local_allowed_networks:
            return

        if ip is None:
            raise InvalidCredentialsError(
                "LOCAL 认证缺少客户端 IP"
            )

        try:
            client_ip = ip_address(
                ip
            )
        except ValueError as exc:
            raise InvalidCredentialsError(
                "LOCAL 认证客户端 IP 无效"
            ) from exc

        if not any(
                client_ip in network
                for network in self.local_allowed_networks
        ):
            raise InvalidCredentialsError(
                "当前网络不允许使用 LOCAL 认证"
            )

    async def _build_authenticated_user(
            self,
            user: User,
    ) -> AuthenticatedUser:
        """构造已认证用户信息"""
        roles, permissions = (
            await self._load_roles_and_permissions(
                user.user_id
            )
        )

        return AuthenticatedUser(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            status=UserStatus(
                user.status
            ),
            roles=roles,
            permissions=permissions,
        )

    async def _load_roles_and_permissions(
            self,
            user_id: str,
    ) -> tuple[
        list[str],
        list[str],
    ]:
        """加载用户的有效角色和权限"""
        grants = await self.grant_repo.list_active_grants(
            user_id=user_id,
            limit=None,
        )

        role_names: list[str] = []
        permissions: list[str] = []

        for grant in grants:
            role = await self.role_repo.get_role(
                role_id=grant.role_id
            )

            if (
                    role is None
                    or role.status != str(
                        RoleStatus.ACTIVE
                    )
            ):
                continue

            role_names.append(
                role.name
            )
            permissions.extend(
                role.permissions
                or []
            )

        return (
            list(
                dict.fromkeys(
                    role_names
                )
            ),
            list(
                dict.fromkeys(
                    permissions
                )
            ),
        )

    def _validate_user_status(
            self,
            user: User,
            *,
            current_time: datetime,
    ) -> None:
        """校验用户状态"""
        if user.status == str(
                UserStatus.DISABLED
        ):
            raise UserDisabledError()

        if user.status == str(
                UserStatus.LOCKED
        ):
            locked_until = user.locked_until

            if (
                    locked_until is not None
                    and self._to_utc(
                        locked_until
                    ) <= current_time
            ):
                self.user_repo.unlock_user(
                    user
                )
                return

            raise UserLockedError()

        if user.status != str(
                UserStatus.ACTIVE
        ):
            raise InvalidCredentialsError()

    @staticmethod
    def _normalize_current_time(
            value: datetime | None,
    ) -> datetime:
        """获取 UTC 当前时间"""
        if value is None:
            return datetime.now(
                timezone.utc
            )

        return AuthService._to_utc(
            value
        )

    @staticmethod
    def _to_utc(
            value: datetime,
    ) -> datetime:
        """转换为 UTC 时间"""
        if (
                value.tzinfo is None
                or value.utcoffset() is None
        ):
            raise ValueError(
                "datetime 必须包含时区信息"
            )

        return value.astimezone(
            timezone.utc
        )


__all__ = [
    "AuthService",
]
