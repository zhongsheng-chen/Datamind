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
from rich.console import Console

from datamind.auth.errors import AuthError
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import (
    LoginRequest,
    LogoutRequest,
)
from datamind.cli.credentials import CredentialStore
from datamind.cli.errors import CredentialError
from datamind.db.core import UnitOfWork
from datamind.utils.network import get_host_ip, get_hostname

console = Console()

logger = structlog.get_logger(__name__)


def login(
        username: str | None = typer.Option(
            None,
            "--username",
            help="登录用户名",
        ),
) -> None:
    """使用本地用户名和密码登录"""
    async def runner() -> None:
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
        logger.info(
            "开始 CLI 登录",
            username=resolved_username,
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

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            tokens = await service.login(
                LoginRequest(
                    username=resolved_username,
                    password=SecretStr(
                        password
                    ),
                ),
                ip=get_host_ip(),
                hostname=get_hostname(),
                user_agent="datamind-cli",
            )

            if (
                    previous_credentials is not None
                    and previous_credentials.refresh_token is not None
            ):
                previous_session_revoked = await service.logout(
                    LogoutRequest(
                        refresh_token=SecretStr(
                            previous_credentials.refresh_token
                        ),
                    )
                )

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

        console.print(
            "[green]登录成功[/green]"
        )

        if tokens.refresh_token is None:
            console.print(
                "[yellow]当前账户不支持自动续期[/yellow]"
            )

        if os.environ.get(
                "DATAMIND_ACCESS_TOKEN",
                "",
        ).strip():
            console.print(
                "[yellow]当前终端设置了 "
                "DATAMIND_ACCESS_TOKEN，"
                "业务命令将优先使用环境变量令牌[/yellow]"
            )

    try:
        asyncio.run(
            runner()
        )
    except (
        AuthError,
        CredentialError,
    ) as exc:
        logger.warning(
            "CLI 登录失败",
            username=username,
            error=str(exc),
        )
        console.print(
            f"[red]登录失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
