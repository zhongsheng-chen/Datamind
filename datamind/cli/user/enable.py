# datamind/cli/user/enable.py

"""启用用户命令

提供 LOCAL 用户启用功能。

核心功能：
  - enable_user: 启用用户

使用示例：
  python -m datamind.cli.main user enable alice
"""

import asyncio

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="启用用户命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("enable")
def enable_user(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
) -> None:
    """启用用户"""
    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始启用用户",
                username=username,
            )

            result = await IdentityService().enable_user(
                username=username,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.print(
                f"[green]用户已启用：{result['username']}[/green]"
            )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.print(
            f"[red]启用用户失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
