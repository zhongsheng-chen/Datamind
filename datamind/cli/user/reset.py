# datamind/cli/user/reset.py

"""重置用户密码命令

提供 LOCAL 用户密码重置和会话撤销功能。

核心功能：
  - reset_password: 重置用户密码

使用示例：
  python -m datamind.cli.main user reset-password alice
"""

import asyncio

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.cli.common import cli_context
from datamind.cli.credentials import CredentialStore
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="重置用户密码命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("reset-password")
def reset_password(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
) -> None:
    """重置用户密码"""
    password = typer.prompt(
        "新密码",
        hide_input=True,
        confirmation_prompt="确认新密码",
    )

    async def runner() -> bool:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始重置用户密码",
                username=username,
            )

            await IdentityService().reset_password(
                username=username,
                password=password,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )

            return context.user == username.strip()

    try:
        reset_current_user = asyncio.run(
            runner()
        )

        if reset_current_user:
            CredentialStore().clear()
            console.warning(
                "当前用户密码已重置，"
                "本地会话已清除，请重新登录"
            )
        else:
            console.info(
                f"用户密码已重置：{username}"
            )
    except (
        IdentityError,
        ValueError,
    ) as exc:
        console.error(
            f"重置密码失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
