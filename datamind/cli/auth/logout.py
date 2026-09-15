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

from datamind.auth.errors import AuthError
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import LogoutRequest
from datamind.cli.credentials import CredentialStore
from datamind.cli.errors import CredentialError
from datamind.cli.common import cli_command_scope
from datamind.cli.output import CLIConsole
from datamind.context import update_context
from datamind.db.core import UnitOfWork
from datamind.utils.network import get_host_ip, get_hostname

console = CLIConsole()

logger = structlog.get_logger(__name__)


def logout() -> None:
    """退出当前登录"""
    client_ip = get_host_ip()
    hostname = get_hostname()
    actor_username = "anonymous"

    async def runner() -> None:
        nonlocal actor_username

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            logger.info(
                "CLI 当前没有本地登录会话"
            )
            console.warning(
                "当前没有本地登录会话"
            )

            if os.environ.get(
                    "DATAMIND_ACCESS_TOKEN",
                    "",
            ).strip():
                console.warning(
                    "当前终端仍设置了 "
                    "DATAMIND_ACCESS_TOKEN，"
                    "请手工清除该环境变量",
                )

            return

        revoked = False

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            try:
                current_user = (
                    await service.authenticate_access_token(
                        credentials.access_token
                    )
                )
            except AuthError:
                current_user = None

            if current_user is not None:
                actor_username = current_user.username
                update_context(
                    user=actor_username,
                )

            logger.debug(
                "开始 CLI 退出登录"
            )

            if credentials.refresh_token is not None:
                logout_result = await service.logout(
                    LogoutRequest(
                        refresh_token=SecretStr(
                            credentials.refresh_token
                        ),
                    )
                )
                revoked = logout_result.revoked

                if current_user is None:
                    actor_username = (
                        logout_result.username
                        or logout_result.user_id
                        or actor_username
                    )
                    update_context(
                        user=actor_username,
                    )

        store.clear()
        logger.info(
            "CLI 退出登录完成",
            action="auth.logout",
            status="success",
            exit_code=0,
            revoked=revoked,
        )

        console.info("已退出登录")

        if (
                credentials.refresh_token is not None
                and not revoked
        ):
            console.warning(
                "刷新令牌此前已失效"
            )

        if os.environ.get(
                "DATAMIND_ACCESS_TOKEN",
                "",
        ).strip():
            console.warning(
                "当前终端仍设置了 "
                "DATAMIND_ACCESS_TOKEN，"
                "请手工清除该环境变量",
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
                "CLI 退出登录失败",
                action="auth.logout",
                status="failed",
                exit_code=1,
                error=str(exc),
            )
            console.error(
                f"退出登录失败：{exc}",
            )
            raise typer.Exit(
                code=1
            ) from None
