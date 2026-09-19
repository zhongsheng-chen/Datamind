"""查看用户命令

提供 LOCAL 用户详情查询功能。

核心功能：
  - show_user: 查看用户

使用示例：
  python -m datamind.cli.main user show alice
"""

import asyncio
import json

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.cli.common import cli_context
from datamind.config import get_logging_config
from datamind.services.identity import IdentityService
from datamind.services.errors import IdentityError
from datamind.utils.datetime import (
    format_datetime,
    parse_datetime,
)


app = typer.Typer(help="查看用户命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_user(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="允许查看已删除用户",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """查看用户"""
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
                "开始查询用户",
                username=username,
                include_deleted=include_deleted,
            )

            result = await IdentityService().get_user(
                username=username,
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
                "用户详情输出完成",
                username=username,
                output=output,
            )
            return

        timezone_name = get_logging_config().timezone
        roles = (
            ", ".join(
                result["roles"]
            )
            or "-"
        )
        last_login_at = format_datetime(
            parse_datetime(
                result["last_login_at"]
            ),
            timezone_name=timezone_name,
        )
        created_at = format_datetime(
            parse_datetime(
                result["created_at"]
            ),
            timezone_name=timezone_name,
        )

        console.info("用户详情\n")
        console.print(
            f"{'USER ID':<16} : "
            f"{result['user_id']}"
        )
        console.print(
            f"{'USERNAME':<16} : "
            f"{result['username']}"
        )
        console.print(
            f"{'DISPLAY NAME':<16} : "
            f"{result['display_name'] or '-'}"
        )
        console.print(
            f"{'EMAIL':<16} : "
            f"{result['email'] or '-'}"
        )
        console.print(
            f"{'STATUS':<16} : "
            f"{result['status']}"
        )
        console.print(
            f"{'ROLES':<16} : "
            f"{roles}"
        )
        console.print(
            f"{'LAST LOGIN AT':<16} : "
            f"{last_login_at or '-'}"
        )
        console.print(
            f"{'CREATED AT':<16} : "
            f"{created_at or '-'}"
        )

        logger.info(
            "用户详情输出完成",
            username=username,
            output=output,
        )

    try:
        asyncio.run(
            runner()
        )
    except IdentityError as exc:
        console.error(
            f"查看用户失败：{exc}",
            output_format=output,
            error_type=type(exc).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
