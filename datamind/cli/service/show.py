# datamind/cli/service/show.py

"""查看服务详情"""

import asyncio
import typer
import structlog
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="查看服务详情")
console = Console()
logger = structlog.get_logger(__name__)


@app.command("show")
def show_service(
    deployment_id: str = typer.Argument(..., help="部署 ID"),
    verbose: bool = typer.Option(False, "--verbose", help="调试模式"),
):
    """查看服务详情"""

    async def _run():
        manager = RuntimeManager()

        service = await manager.get(deployment_id)

        if not service:
            console.print("[red]服务不存在[/red]")
            return

        console.print("[green]服务详情[/green]\n")

        console.print(f"DEPLOYMENT ID : {service['deployment_id']}")
        console.print(f"MODEL ID      : {service.get('model_id')}")
        console.print(f"ENDPOINT      : {service.get('endpoint')}")
        console.print(f"STATUS        : {service['status']}")

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())