# datamind/cli/role/disable.py

"""停用角色命令

提供角色停用功能。

核心功能：
  - disable_role: 停用角色

使用示例：
  python -m datamind.cli.main role disable developer
"""

import asyncio

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="停用角色命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("disable")
def disable_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
) -> None:
    """停用角色"""
    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始停用角色",
                name=name,
            )

            result = await IdentityService().disable_role(
                name=name,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.info(
                f"角色已停用：{result['name']}"
            )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.error(
            f"停用角色失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
