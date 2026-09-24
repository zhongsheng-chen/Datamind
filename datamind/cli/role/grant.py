"""授予角色命令.

提供授予用户角色的功能。

核心功能：
  - grant_role: 授予用户角色

使用示例：
  python -m datamind.cli.main role grant alice developer
"""

import asyncio

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.identity import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="授予角色命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("grant")
def grant_role(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
        role_name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
) -> None:
    """授予用户角色."""
    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始授予用户角色",
                username=username,
                role_name=role_name,
            )

            result = await IdentityService().grant_role(
                username=username,
                role_name=role_name,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.info(
                "角色授予成功："
                f"{result['username']} -> {result['role']}"
            )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.error(
            f"授予角色失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
