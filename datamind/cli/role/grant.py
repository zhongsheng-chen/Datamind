# datamind/cli/role/grant.py

"""授予角色命令

提供向用户授予角色的功能。

核心功能：
  - grant_role: 向用户授予角色

使用示例：
  python -m datamind.cli.main role grant alice developer
"""

import asyncio

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="授予角色命令")
console = Console()

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
    """向用户授予角色"""
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
            console.print(
                "[green]角色授予成功："
                f"{result['username']} -> {result['role']}[/green]"
            )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.print(
            f"[red]授予角色失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
