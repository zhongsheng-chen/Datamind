# datamind/cli/auth/logout.py

"""退出登录命令

提供本地 CLI 会话退出功能。

核心功能：
  - logout: 撤销刷新令牌

使用示例：
  python -m datamind.cli.main logout
"""

import asyncio
import os

import structlog
import typer
from pydantic import SecretStr
from rich.console import Console

from datamind.auth.errors import AuthError
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import LogoutRequest
from datamind.cli.credentials import CredentialStore
from datamind.cli.errors import CredentialError
from datamind.db.core import UnitOfWork

console = Console()

logger = structlog.get_logger(__name__)


def logout() -> None:
    """退出当前登录"""
    async def runner() -> None:
        logger.info(
            "开始 CLI 退出登录"
        )
        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            logger.info(
                "CLI 当前没有本地登录会话"
            )
            console.print(
                "[yellow]当前没有本地登录会话[/yellow]"
            )

            if os.environ.get(
                    "DATAMIND_ACCESS_TOKEN",
                    "",
            ).strip():
                console.print(
                    "[yellow]当前终端仍设置了 "
                    "DATAMIND_ACCESS_TOKEN，"
                    "请手工清除该环境变量[/yellow]"
                )

            return

        revoked = False

        if credentials.refresh_token is not None:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )
                revoked = await service.logout(
                    LogoutRequest(
                        refresh_token=SecretStr(
                            credentials.refresh_token
                        ),
                    )
                )

        store.clear()
        logger.info(
            "CLI 退出登录完成",
            refresh_token_revoked=revoked,
        )

        console.print(
            "[green]已退出登录[/green]"
        )

        if (
                credentials.refresh_token is not None
                and not revoked
        ):
            console.print(
                "[yellow]刷新令牌此前已失效[/yellow]"
            )

        if os.environ.get(
                "DATAMIND_ACCESS_TOKEN",
                "",
        ).strip():
            console.print(
                "[yellow]当前终端仍设置了 "
                "DATAMIND_ACCESS_TOKEN，"
                "请手工清除该环境变量[/yellow]"
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
            "CLI 退出登录失败",
            error=str(exc),
        )
        console.print(
            f"[red]退出登录失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
