# datamind/cli/auth/login.py

"""登录命令

提供本地 CLI 会话登录和用户切换功能。

核心功能：
  - login: 登录并替换本地 CLI 会话

使用示例：
  python -m datamind.cli.main login --username alice
"""

import asyncio
import os

import structlog
import typer
from pydantic import SecretStr

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    TokenResponse,
)
from datamind.cli.credentials import CredentialStore
from datamind.cli.errors import CredentialError
from datamind.cli.common import cli_command_scope
from datamind.cli.output import CLIConsole
from datamind.context import update_context
from datamind.db.core import UnitOfWork
from datamind.utils.network import get_host_ip, get_hostname

console = CLIConsole()

logger = structlog.get_logger(__name__)


def login(
        username: str | None = typer.Option(
            None,
            "--username",
            help="登录用户名",
        ),
) -> None:
    """使用本地用户名和密码登录"""
    client_ip = get_host_ip()
    hostname = get_hostname()
    actor_username = "anonymous"

    async def runner() -> None:
        nonlocal actor_username

        resolved_username = (
            username
            or typer.prompt(
                "登录用户名"
            )
        )
        password = typer.prompt(
            "登录密码",
            hide_input=True,
        )
        store = CredentialStore()

        try:
            previous_credentials = store.load()
        except CredentialError as credential_error:
            previous_credentials = None
            logger.warning(
                "已有 CLI 登录凭据无效，将直接替换",
                error=str(credential_error),
            )

        previous_session_revoked = False
        tokens: TokenResponse | None = None
        login_error: (
            InvalidCredentialsError
            | UserDisabledError
            | UserLockedError
            | None
        ) = None

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            if previous_credentials is not None:
                try:
                    current_user = (
                        await service.authenticate_access_token(
                            previous_credentials.access_token
                        )
                    )
                except AuthError:
                    current_user = None

                if current_user is not None:
                    actor_username = current_user.username
                    update_context(
                        user=actor_username,
                    )

            logger.info(
                "开始 CLI 登录",
                username=resolved_username,
            )
            try:
                tokens = await service.login(
                    LoginRequest(
                        username=resolved_username,
                        password=SecretStr(
                            password
                        ),
                    ),
                    ip=client_ip,
                    hostname=hostname,
                    user_agent="datamind-cli",
                )
            except (
                    InvalidCredentialsError,
                    UserDisabledError,
                    UserLockedError,
            ) as authentication_error:
                login_error = authentication_error

            if (
                    login_error is None
                    and previous_credentials is not None
                    and previous_credentials.refresh_token is not None
            ):
                previous_session_revoked = await service.logout(
                    LogoutRequest(
                        refresh_token=SecretStr(
                            previous_credentials.refresh_token
                        ),
                    )
                )

        if login_error is not None:
            raise login_error

        if tokens is None:
            raise AuthError(
                "登录服务未返回有效凭据"
            )

        update_context(
            user=resolved_username,
        )
        actor_username = resolved_username
        store.save(
            tokens
        )
        logger.info(
            "CLI 登录成功",
            username=resolved_username,
            expires_in=tokens.expires_in,
            previous_session_revoked=(
                previous_session_revoked
            ),
        )

        console.info("登录成功")

        if tokens.refresh_token is None:
            console.warning(
                "当前账户不支持自动续期"
            )

        if os.environ.get(
                "DATAMIND_ACCESS_TOKEN",
                "",
        ).strip():
            console.warning(
                "当前终端设置了 "
                "DATAMIND_ACCESS_TOKEN，"
                "业务命令将优先使用环境变量令牌",
            )

    with cli_command_scope(
            ip=client_ip,
            hostname=hostname,
    ):
        try:
            asyncio.run(
                runner()
            )
        except (
            AuthError,
            CredentialError,
        ) as exc:
            update_context(
                user=actor_username,
            )
            logger.warning(
                "CLI 登录失败",
                username=username,
                error=str(exc),
            )
            console.error(
                f"登录失败：{exc}",
            )
            raise typer.Exit(
                code=1
            ) from None
