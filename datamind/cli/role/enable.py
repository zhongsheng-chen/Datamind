"""启用角色命令

提供角色启用功能。

核心功能：
  - enable_role: 启用角色

使用示例：
  python -m datamind.cli.main role enable developer
"""

import asyncio

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.identity import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="启用角色命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("enable")
def enable_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
) -> None:
    """启用角色"""
    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始启用角色",
                name=name,
            )

            result = await IdentityService().enable_role(
                name=name,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.info(
                f"角色已启用：{result['name']}"
            )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.error(
            f"启用角色失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
