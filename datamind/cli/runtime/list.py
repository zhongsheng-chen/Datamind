"""运行状态列表命令.

提供部署运行状态列表查询功能。

核心功能：
  - list_runtimes: 查询部署运行状态列表

使用示例：
  python -m datamind.cli.main runtime list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.config import get_service_config
from datamind.services.control import RuntimeControlService
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="运行状态列表命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_runtimes(
        desired_status: str | None = typer.Option(
            None,
            "--desired-status",
            help="按期望运行状态过滤，可选值：loaded / unloaded"
        ),
        limit: int = typer.Option(
            10,
            "--limit",
            help="返回记录数量限制"
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            help="分页偏移量"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """查询部署运行状态列表."""
    environment = get_service_config().environment.value

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if desired_status not in (
                None,
                "loaded",
                "unloaded",
        ):
            raise typer.BadParameter(
                "--desired-status 只支持 loaded 或 unloaded"
            )

        if limit <= 0:
            raise typer.BadParameter(
                "--limit 必须大于 0"
            )

        if offset < 0:
            raise typer.BadParameter(
                "--offset 不能小于 0"
            )

        logger.info(
            "开始查询部署运行状态列表",
            environment=environment,
            desired_status=desired_status,
            limit=limit,
            offset=offset,
        )

        controller = RuntimeControlService()

        services = await controller.list_services(
            environment=environment,
            desired_status=desired_status,
            limit=limit,
            offset=offset,
        )

        result = []

        for item in services:
            result.append({
                **item,
                "updated_at": format_iso_utc(
                    parse_datetime(
                        item["updated_at"]
                    )
                ),
                "runtimes": [
                    {
                        **runtime,
                        "loaded_at": format_iso_utc(
                            parse_datetime(
                                runtime["loaded_at"]
                            )
                        ),
                        "unloaded_at": format_iso_utc(
                            parse_datetime(
                                runtime["unloaded_at"]
                            )
                        ),
                        "last_heartbeat_at": format_iso_utc(
                            parse_datetime(
                                runtime["last_heartbeat_at"]
                            )
                        ),
                    }
                    for runtime in item["runtimes"]
                ],
            })

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            return result

        console.print(
            f"[dim]共找到 {len(result)} 个运行状态[/dim]\n"
        )

        if not result:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("CONTROL ID")
        table.add_column("DEPLOYMENT ID")
        table.add_column("ENVIRONMENT")
        table.add_column("DESIRED STATUS")
        table.add_column("GENERATION")
        table.add_column("WORKERS")
        table.add_column("RUNTIMES")
        table.add_column("STARTING")
        table.add_column("RUNNING")
        table.add_column("STOPPING")
        table.add_column("STOPPED")
        table.add_column("FAILED")
        table.add_column("UPDATED BY")
        table.add_column("UPDATED AT")

        for item in result:
            table.add_row(
                str(item["control_id"]),
                str(item["deployment_id"]),
                str(item["environment"]),
                str(item["desired_status"]),
                str(item["generation"]),
                str(item["worker_count"]),
                str(item["runtime_count"]),
                str(item["starting_count"]),
                str(item["running_count"]),
                str(item["stopping_count"]),
                str(item["stopped_count"]),
                str(item["failed_count"]),
                str(item["updated_by"] or "-"),
                format_datetime(
                    parse_datetime(
                        item["updated_at"]
                    )
                ),
            )

        console.print(table)

        return result

    async def runner():
        async with cli_context(
                required_permission="runtime.read",
        ):
            try:
                await _run()
            except ValueError as error:
                logger.warning(
                    "运行状态列表查询失败",
                    environment=environment,
                    desired_status=desired_status,
                    error=str(error),
                )
                console.error(
                    f"运行状态查询失败：{error}",
                    output_format=output,
                    error_type=type(error).__name__,
                )
                raise typer.Exit(code=1) from None

    asyncio.run(runner())
