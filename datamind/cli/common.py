# datamind/cli/common.py

"""CLI 公共模块

提供 CLI 命令的通用上下文管理。

核心功能：
  - cli_context: CLI 上下文管理器

使用示例：
  from datamind.cli.common import cli_context

  async with cli_context(
      required_permission="model.read",
      ip="10.0.0.1",
  ) as context:
      print(context.user)
"""

import os
import uuid
from contextlib import AbstractContextManager

import structlog
import typer
from pydantic import SecretStr
from rich.console import Console

from datamind.auth.errors import (
    AuthenticationRequiredError,
    AuthError,
    InvalidAccessTokenError,
    TokenError,
)
from datamind.auth.factory import create_auth_service
from datamind.auth.permissions import require_permission
from datamind.auth.schemas import (
    AuthenticatedUser,
    RefreshTokenRequest,
    TokenResponse,
)
from datamind.cli.credentials import CredentialStore
from datamind.cli.errors import CredentialError
from datamind.config import get_settings
from datamind.constants import Environment
from datamind.context.scope import context_scope
from datamind.db.core import UnitOfWork
from datamind.logging import setup_logging
from datamind.utils.network import get_host_ip, get_hostname


console = Console()
logger = structlog.get_logger(__name__)


class CLIContext:
    """CLI 上下文"""

    def __init__(
            self,
            *,
            required_permission: str | None = None,
            ip: str | None = None,
            hostname: str | None = None,
    ):
        """初始化 CLI 上下文

        参数：
            required_permission: 执行命令所需权限（可选）
            ip: 客户端 IP 地址，默认自动获取
            hostname: 客户端名称，默认自动获取
        """
        self.required_permission = required_permission
        self.user = "system"
        self.ip = ip or get_host_ip()
        self.hostname = hostname or get_hostname()

        self.settings = get_settings()

        self.scope: AbstractContextManager[None] | None = None

        self.authenticated_user: AuthenticatedUser | None = None

    async def __aenter__(self):
        """进入上下文

        初始化日志系统并创建上下文作用域。

        返回：
            CLIContext 实例
        """
        logging_config = self.settings.logging
        setup_logging(
            logging_config
        )

        try:
            await self._authenticate()
        except (
            AuthError,
            CredentialError,
        ) as exc:
            logger.warning(
                "CLI 身份认证失败",
                required_permission=self.required_permission,
                error=str(exc),
            )
            console.print(
                f"[red]认证失败：{exc}[/red]"
            )
            raise typer.Exit(
                code=1
            ) from None

        # 创建上下文作用域
        scope = context_scope(
            user=self.user,
            ip=self.ip,
            hostname=self.hostname,
            trace_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            source="cli",
        )
        scope.__enter__()
        self.scope = scope

        return self

    async def _authenticate(self) -> None:
        """认证 CLI 操作人

        开发和测试环境允许在认证关闭时使用本地维护模式，
        预发布和生产环境必须启用认证。启用认证后，优先使用
        DATAMIND_ACCESS_TOKEN；未提供时使用本地 CLI 登录凭据。
        本地访问令牌失效时，使用刷新令牌续期并保存新凭据。
        """
        auth_config = self.settings.auth
        environment = self.settings.service.environment

        if not auth_config.enabled:
            if environment in (
                    Environment.STAGING,
                    Environment.PRODUCTION,
            ):
                raise AuthError(
                    "预发布和生产环境必须启用认证"
                )

            return

        environment_token = os.environ.get(
            "DATAMIND_ACCESS_TOKEN",
            "",
        ).strip()

        if environment_token:
            authenticated_user = (
                await self._authenticate_environment_token(
                    environment_token
                )
            )
        else:
            authenticated_user = (
                await self._authenticate_stored_credentials()
            )

        if self.required_permission is not None:
            require_permission(
                granted_permissions=(
                    authenticated_user.permissions
                ),
                required_permission=(
                    self.required_permission
                ),
            )

        self.authenticated_user = authenticated_user
        self.user = authenticated_user.username

    @staticmethod
    async def _authenticate_environment_token(
            access_token: str,
    ) -> AuthenticatedUser:
        """认证环境变量提供的访问令牌"""
        authenticated_user: AuthenticatedUser | None = None

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            authenticated_user = (
                await service.authenticate_access_token(
                    access_token
                )
            )

        if authenticated_user is None:
            raise InvalidAccessTokenError()

        return authenticated_user

    async def _authenticate_stored_credentials(
            self,
    ) -> AuthenticatedUser:
        """认证并按需续期本地 CLI 登录凭据"""
        store = CredentialStore()

        try:
            credentials = store.load()
        except CredentialError as exc:
            raise AuthenticationRequiredError(
                str(exc)
            ) from exc

        if credentials is None:
            raise AuthenticationRequiredError(
                "尚未登录，请执行 "
                "datamind login"
            )

        refreshed_tokens: TokenResponse | None = None

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )

            try:
                authenticated_user = (
                    await service.authenticate_access_token(
                        credentials.access_token
                    )
                )
            except InvalidAccessTokenError:
                if credentials.refresh_token is None:
                    store.clear()
                    raise AuthenticationRequiredError(
                        "登录会话已过期，请重新登录"
                    ) from None

                try:
                    new_tokens = await service.refresh(
                        RefreshTokenRequest(
                            refresh_token=SecretStr(
                                credentials.refresh_token
                            ),
                        ),
                        ip=self.ip,
                        hostname=self.hostname,
                        user_agent="datamind-cli",
                    )
                except TokenError:
                    store.clear()
                    raise AuthenticationRequiredError(
                        "登录会话已失效，请重新登录"
                    ) from None

                authenticated_user = (
                    await service.authenticate_access_token(
                        new_tokens.access_token
                    )
                )
                refreshed_tokens = new_tokens

        if refreshed_tokens is not None:
            try:
                store.save(
                    refreshed_tokens
                )
            except CredentialError as exc:
                raise AuthError(
                    str(exc)
                ) from exc

        return authenticated_user

    async def __aexit__(self, exc_type, exc, tb):
        """退出上下文

        恢复上下文作用域。
        """
        if self.scope is not None:
            self.scope.__exit__(exc_type, exc, tb)


def cli_context(
        *,
        required_permission: str | None = None,
        ip: str | None = None,
        hostname: str | None = None,
) -> CLIContext:
    """CLI 上下文管理器

    参数：
        required_permission: 执行命令所需权限（可选）
        ip: 客户端 IP
        hostname: 客户端名称

    返回：
        CLIContext 实例
    """
    return CLIContext(
        required_permission=required_permission,
        ip=ip,
        hostname=hostname,
    )
