"""列出用户命令.

提供 LOCAL 用户列表查询功能。

核心功能：
  - list_users: 列出用户

使用示例：
  python -m datamind.cli.main user list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.auth.enums import UserStatus
from datamind.cli.common import cli_context
from datamind.config import get_logging_config
from datamind.services.identity import IdentityService
from datamind.utils.datetime import (
    format_datetime,
    parse_datetime,
)


app = typer.Typer(help="列出用户命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_users(
        status: str | None = typer.Option(
            None,
            "--status",
            help="用户状态：active / disabled / locked",
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除用户",
        ),
        limit: int = typer.Option(
            100,
            "--limit",
            help="返回记录数量限制",
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            help="分页偏移量",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """列出用户."""
    async def runner() -> None:
        parsed_status = (
            UserStatus(
                status
            )
            if status is not None
            else None
        )

        async with cli_context(
                required_permission="identity.read",
        ):
            logger.info(
                "开始列出用户",
                status=parsed_status,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )

            result = await IdentityService().list_users(
                status=parsed_status,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
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
                "用户列表输出完成",
                count=len(result),
                output=output,
            )
            return

        console.print(
            f"[dim]共找到 {len(result)} 个用户[/dim]\n"
        )

        if not result:
            logger.info(
                "用户列表输出完成",
                count=0,
                output=output,
            )
            return

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )
        table.add_column("USERNAME")
        table.add_column("STATUS")
        table.add_column("DISPLAY NAME")
        table.add_column("ROLES")
        table.add_column("UPDATED AT")
        timezone_name = get_logging_config().timezone

        for item in result:
            table.add_row(
                item["username"],
                item["status"],
                item["display_name"] or "-",
                ", ".join(item["roles"]) or "-",
                format_datetime(
                    parse_datetime(
                        item["updated_at"]
                    ),
                    timezone_name=timezone_name,
                ),
            )

        logger.info(
            "用户列表输出完成",
            count=len(result),
            output=output,
        )

        console.print(
            table
        )

    try:
        asyncio.run(
            runner()
        )
    except ValueError as exc:
        console.error(
            f"列出用户失败：{exc}",
            output_format=output,
            error_type=type(exc).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
