# datamind/cli/service/list.py

"""服务列表命令

提供运行服务状态列表查询功能。

核心功能：
  - list_services: 查询运行服务列表

使用示例：
  python -m datamind.cli.main service list
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.services import RuntimeController

app = typer.Typer(help="服务列表命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_services(
    desired_status: str | None = typer.Option(
        None,
        "--desired-status",
        help="期望运行状态：loaded/unloaded"
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="返回数量限制"
    ),
    offset: int | None = typer.Option(
        None,
        "--offset",
        help="分页偏移量"
    ),
    output: str = typer.Option(
        "table",
        "--format",
        help="输出格式：table/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示调试日志"
    ),
):
    """查询运行服务列表"""

    async def _run():
        if output not in ("table", "json"):
            raise typer.BadParameter(
                "--format 只支持 table 或 json"
            )

        if desired_status not in (
            None,
            "loaded",
            "unloaded",
        ):
            raise typer.BadParameter(
                "--desired-status 只支持 loaded 或 unloaded"
            )

        if limit is not None and limit <= 0:
            raise typer.BadParameter(
                "--limit 必须大于 0"
            )

        if offset is not None and offset < 0:
            raise typer.BadParameter(
                "--offset 不能小于 0"
            )

        logger.info(
            "开始查询运行服务列表",
            desired_status=desired_status,
            limit=limit,
            offset=offset,
        )

        controller = RuntimeController()

        result = await controller.list_services(
            desired_status=desired_status,
            limit=limit,
            offset=offset,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return

        if not result:
            console.print(
                "[yellow]未找到运行服务记录[/yellow]"
            )
            return

        table = Table(
            title="Runtime Services"
        )

        table.add_column(
            "CONTROL ID",
            style="cyan",
        )
        table.add_column(
            "DEPLOYMENT ID",
        )
        table.add_column(
            "DESIRED",
        )
        table.add_column(
            "GENERATION",
            justify="right",
        )
        table.add_column(
            "WORKERS",
            justify="right",
        )
        table.add_column(
            "LOADING",
            justify="right",
        )
        table.add_column(
            "LOADED",
            justify="right",
        )
        table.add_column(
            "UNLOADED",
            justify="right",
        )
        table.add_column(
            "FAILED",
            justify="right",
        )
        table.add_column(
            "UPDATED BY",
        )
        table.add_column(
            "UPDATED AT",
        )

        for item in result:
            table.add_row(
                str(item["control_id"]),
                str(item["deployment_id"]),
                str(item["desired_status"]),
                str(item["generation"]),
                str(item["worker_count"]),
                str(item["loading_count"]),
                str(item["loaded_count"]),
                str(item["unloaded_count"]),
                str(item["failed_count"]),
                str(item["updated_by"] or ""),
                str(item["updated_at"] or ""),
            )

        console.print(table)

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())