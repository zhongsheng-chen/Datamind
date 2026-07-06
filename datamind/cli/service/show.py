# datamind/cli/service/show.py

"""查看服务状态命令

提供指定部署的运行状态查询功能。

核心功能：
  - show_service: 查看部署服务运行状态

使用示例：
  python -m datamind.cli.main service show dep_a1b2c3d4
"""

import asyncio
import json

import structlog
import typer
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.services import RuntimeController
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="查看服务状态命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_service(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text/json"
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="显示调试日志"
        ),
):
    """查看部署服务运行状态"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始查询部署服务状态",
            deployment_id=deployment_id,
        )

        controller = RuntimeController()

        result = await controller.get_status(
            deployment_id=deployment_id,
        )

        deployment = result["deployment"]
        control = result["control"]
        runtimes = result["runtimes"]

        if output == "json":
            json_result = {
                "deployment": deployment,
                "control": (
                    {
                        **control,
                        "created_at": format_iso_utc(
                            parse_datetime(
                                control["created_at"]
                            )
                        ),
                        "updated_at": format_iso_utc(
                            parse_datetime(
                                control["updated_at"]
                            )
                        ),
                    }
                    if control is not None
                    else None
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
                    for runtime in runtimes
                ],
            }

            console.print_json(
                json.dumps(
                    json_result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

            return json_result

        console.print(
            "[green]服务详情[/green]\n"
        )

        console.print(
            f"[cyan]{'DEPLOYMENT ID':<18}[/cyan] : "
            f"{deployment['deployment_id']}"
        )
        console.print(
            f"[cyan]{'MODEL ID':<18}[/cyan] : "
            f"{deployment['model_id']}"
        )
        console.print(
            f"[cyan]{'VERSION ID':<18}[/cyan] : "
            f"{deployment['version_id']}"
        )
        console.print(
            f"[cyan]{'FRAMEWORK':<18}[/cyan] : "
            f"{deployment['framework']}"
        )
        console.print(
            f"[cyan]{'ENVIRONMENT':<18}[/cyan] : "
            f"{deployment['environment']}"
        )
        console.print(
            f"[cyan]{'ROLLOUT TYPE':<18}[/cyan] : "
            f"{deployment['rollout_type']}"
        )
        console.print(
            f"[cyan]{'ROLE':<18}[/cyan] : "
            f"{deployment['role']}"
        )
        console.print(
            f"[cyan]{'STATUS':<18}[/cyan] : "
            f"{deployment['status']}"
        )

        console.print()

        if control is None:
            console.print(
                "[yellow]暂无运行控制记录[/yellow]\n"
            )

        else:
            console.print(
                f"[cyan]{'CONTROL ID':<18}[/cyan] : "
                f"{control['control_id']}"
            )
            console.print(
                f"[cyan]{'DESIRED STATUS':<18}[/cyan] : "
                f"{control['desired_status']}"
            )
            console.print(
                f"[cyan]{'GENERATION':<18}[/cyan] : "
                f"{control['generation']}"
            )
            console.print(
                f"[cyan]{'CREATED BY':<18}[/cyan] : "
                f"{control['created_by'] or '-'}"
            )
            console.print(
                f"[cyan]{'CREATED AT':<18}[/cyan] : "
                f"{format_datetime(parse_datetime(control['created_at']))}"
            )
            console.print(
                f"[cyan]{'UPDATED BY':<18}[/cyan] : "
                f"{control['updated_by'] or '-'}"
            )
            console.print(
                f"[cyan]{'UPDATED AT':<18}[/cyan] : "
                f"{format_datetime(parse_datetime(control['updated_at']))}"
            )

            console.print()

        console.print(
            f"[dim]共找到 {len(runtimes)} 个 Worker 运行记录[/dim]\n"
        )

        if not runtimes:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("RUNTIME ID")
        table.add_column("WORKER ID")
        table.add_column("STATUS")
        table.add_column("LOADED AT")
        table.add_column("UNLOADED AT")
        table.add_column("HEARTBEAT")
        table.add_column("ERROR")

        for runtime in runtimes:
            table.add_row(
                str(runtime["runtime_id"]),
                str(runtime["worker_id"]),
                str(runtime["status"]),
                format_datetime(
                    parse_datetime(
                        runtime["loaded_at"]
                    )
                ),
                format_datetime(
                    parse_datetime(
                        runtime["unloaded_at"]
                    )
                ),
                format_datetime(
                    parse_datetime(
                        runtime["last_heartbeat_at"]
                    )
                ),
                str(runtime["error"] or "-"),
            )

        console.print(table)

        return result

    async def runner():
        async with cli_context(
                verbose=verbose,
                enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())
