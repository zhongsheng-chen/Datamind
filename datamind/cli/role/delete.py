"""删除角色命令

提供角色逻辑删除功能。

核心功能：
  - delete_role: 删除角色

使用示例：
  python -m datamind.cli.main role delete developer --yes
"""

import asyncio

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.identity import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="删除角色命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
        reason: str | None = typer.Option(
            None,
            "--reason",
            help="删除原因",
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="跳过确认",
        ),
) -> None:
    """逻辑删除角色"""
    if not yes:
        typer.confirm(
            f"确认删除角色 {name}？",
            abort=True,
        )

    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始删除角色",
                name=name,
            )

            result = await IdentityService().delete_role(
                name=name,
                reason=reason,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.info(
                f"角色已删除：{result['name']}"
            )

    try:
        asyncio.run(
            runner()
        )
    except (
        IdentityError,
        ValueError,
    ) as exc:
        console.error(
            f"删除角色失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
