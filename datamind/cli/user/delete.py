"""删除用户命令

提供 LOCAL 用户逻辑删除功能。

核心功能：
  - delete_user: 删除用户

使用示例：
  python -m datamind.cli.main user delete alice --yes
"""

import asyncio

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.cli.common import cli_context
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="删除用户命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_user(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
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
    """逻辑删除用户"""
    if not yes:
        typer.confirm(
            f"确认删除用户 {username}？",
            abort=True,
        )

    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始删除用户",
                username=username,
            )

            result = await IdentityService().delete_user(
                username=username,
                reason=reason,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )
            console.info(
                f"用户已删除：{result['username']}"
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
            f"删除用户失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
