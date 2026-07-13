# datamind/cli/role/create.py

"""创建角色命令

提供角色和权限集合创建功能。

核心功能：
  - create_role: 创建角色

使用示例：
  python -m datamind.cli.main role create developer \
    --permission model.read \
    --permission model.write
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="创建角色命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("create")
def create_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
        permissions: list[str] | None = typer.Option(
            None,
            "--permission",
            help="权限标识，可重复指定",
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="角色说明",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """创建角色"""
    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始创建角色",
                name=name,
                permissions=permissions or [],
            )

            result = await IdentityService().create_role(
                name=name,
                permissions=permissions or [],
                description=description,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
            )
            return

        permission_values = (
            ", ".join(
                result["permissions"]
            )
            or "-"
        )

        console.print(
            "[green]角色创建成功[/green]\n"
        )
        console.print(
            f"[cyan]{'NAME':<16}[/cyan] : "
            f"{result['name']}"
        )
        console.print(
            f"[cyan]{'PERMISSIONS':<16}[/cyan] : "
            f"{permission_values}"
        )

    try:
        asyncio.run(
            runner()
        )
    except (
        IdentityError,
        ValueError,
    ) as exc:
        console.print(
            f"[red]创建角色失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
