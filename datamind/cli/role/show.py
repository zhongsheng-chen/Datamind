# datamind/cli/role/show.py

"""查看角色命令

提供角色详情查询功能。

核心功能：
  - show_role: 查看角色

使用示例：
  python -m datamind.cli.main role show developer
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.services import IdentityService
from datamind.services.errors import IdentityError
from datamind.utils.datetime import (
    format_datetime,
    parse_datetime,
)


app = typer.Typer(help="查看角色命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="允许查看已删除角色",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """查看角色"""
    async def runner() -> None:
        if output not in (
                "text",
                "json",
        ):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        async with cli_context(
                required_permission="identity.read",
        ):
            logger.info(
                "开始查询角色",
                name=name,
                include_deleted=include_deleted,
            )

            result = await IdentityService().get_role(
                name=name,
                include_deleted=include_deleted,
            )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            logger.info(
                "角色详情输出完成",
                name=name,
                output=output,
            )
            return

        timezone_name = get_settings().logging.timezone
        permission_values = (
            ", ".join(
                result["permissions"]
            )
            or "-"
        )
        created_at = format_datetime(
            parse_datetime(
                result["created_at"]
            ),
            timezone_name=timezone_name,
        )

        console.print(
            "[green]角色详情[/green]\n"
        )
        console.print(
            f"[cyan]{'ROLE ID':<16}[/cyan] : "
            f"{result['role_id']}"
        )
        console.print(
            f"[cyan]{'NAME':<16}[/cyan] : "
            f"{result['name']}"
        )
        console.print(
            f"[cyan]{'DESCRIPTION':<16}[/cyan] : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"[cyan]{'STATUS':<16}[/cyan] : "
            f"{result['status']}"
        )
        console.print(
            f"[cyan]{'PERMISSIONS':<16}[/cyan] : "
            f"{permission_values}"
        )
        console.print(
            f"[cyan]{'CREATED AT':<16}[/cyan] : "
            f"{created_at or '-'}"
        )

        logger.info(
            "角色详情输出完成",
            name=name,
            output=output,
        )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.print(
            f"[red]查看角色失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
