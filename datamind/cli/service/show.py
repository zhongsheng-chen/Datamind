# datamind/cli/service/show.py

"""查看服务命令

提供模型运行时服务详情查看功能。

核心功能：
  - show_service: 查看模型服务详情

使用示例：
  python -m datamind.cli.main service show dep_a1b2c3d4
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="查看服务命令")
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
    """查看服务详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看模型服务详情",
            deployment_id=deployment_id,
        )

        manager = RuntimeManager()

        try:
            result = await manager.status(
                deployment_id=deployment_id,
            )
        except RuntimeRouteError as e:
            message = getattr(e, "message", str(e))
            console.print(f"[red]{message}[/red]")
            raise typer.Exit(1)

        runtime = result.get("runtime") or {}
        memory = result.get("memory") or {}

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return result

        console.print("[green]模型服务详情[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<20}[/cyan] : {result.get('deployment_id') or '-'}")
        console.print(f"[cyan]{'WORKER':<20}[/cyan] : {result.get('worker_id') or '-'}")
        console.print(f"[cyan]{'LOADED IN MEMORY':<20}[/cyan] : {result.get('loaded_in_memory')}")
        console.print(f"[cyan]{'RUNTIME ID':<20}[/cyan] : {runtime.get('runtime_id') or '-'}")
        console.print(f"[cyan]{'STATUS':<20}[/cyan] : {runtime.get('status') or '-'}")
        console.print(f"[cyan]{'MODEL ID':<20}[/cyan] : {runtime.get('model_id') or '-'}")
        console.print(f"[cyan]{'VERSION ID':<20}[/cyan] : {runtime.get('version_id') or '-'}")
        console.print(f"[cyan]{'FRAMEWORK':<20}[/cyan] : {runtime.get('framework') or '-'}")
        console.print(f"[cyan]{'LOADED AT':<20}[/cyan] : {runtime.get('loaded_at') or '-'}")
        console.print(f"[cyan]{'UNLOADED AT':<20}[/cyan] : {runtime.get('unloaded_at') or '-'}")
        console.print(f"[cyan]{'HEARTBEAT AT':<20}[/cyan] : {runtime.get('last_heartbeat_at') or '-'}")
        console.print(f"[cyan]{'ERROR':<20}[/cyan] : {runtime.get('error') or '-'}")

        if memory:
            console.print(f"[cyan]{'ACCESS COUNT':<20}[/cyan] : {memory.get('access_count') or 0}")
            console.print(f"[cyan]{'LAST USED AT':<20}[/cyan] : {memory.get('last_used_at') or '-'}")

        return result

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())