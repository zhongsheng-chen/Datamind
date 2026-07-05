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

import typer
import structlog
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.services import RuntimeController

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

        deployment = result["deployment"]
        control = result["control"]
        runtimes = result["runtimes"]

        console.print(
            "[bold cyan]Deployment[/bold cyan]\n"
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

        console.print(
            "[bold cyan]Control[/bold cyan]\n"
        )

        if control is None:
            console.print(
                "[yellow]暂无运行控制记录[/yellow]"
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
                f"{control['created_by']}"
            )
            console.print(
                f"[cyan]{'UPDATED BY':<18}[/cyan] : "
                f"{control['updated_by']}"
            )
            console.print(
                f"[cyan]{'UPDATED AT':<18}[/cyan] : "
                f"{control['updated_at']}"
            )

        console.print()

        console.print(
            "[bold cyan]Runtimes[/bold cyan]\n"
        )

        if not runtimes:
            console.print(
                "[yellow]暂无 Worker 运行记录[/yellow]"
            )
            return

        table = Table()

        table.add_column(
            "RUNTIME ID",
            style="cyan",
        )
        table.add_column(
            "WORKER ID",
        )
        table.add_column(
            "STATUS",
        )
        table.add_column(
            "LOADED AT",
        )
        table.add_column(
            "HEARTBEAT",
        )
        table.add_column(
            "ERROR",
        )

        for runtime in runtimes:
            table.add_row(
                str(runtime["runtime_id"]),
                str(runtime["worker_id"]),
                str(runtime["status"]),
                str(runtime["loaded_at"] or ""),
                str(runtime["last_heartbeat_at"] or ""),
                str(runtime["error"] or ""),
            )

        console.print(table)

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())