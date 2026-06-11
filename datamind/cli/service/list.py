# datamind/cli/service/list.py

"""列出运行服务"""

import asyncio
import typer
import structlog
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="列出运行服务")
console = Console()
logger = structlog.get_logger(__name__)


@app.command("list")
def list_services(
    verbose: bool = typer.Option(False, "--verbose", help="调试模式"),
):
    """列出运行中服务"""

    async def _run():
        manager = RuntimeManager()

        services = await manager.list()

        console.print(f"[dim]运行中服务数: {len(services)}[/dim]\n")

        table = Table()
        table.add_column("DEPLOYMENT ID")
        table.add_column("MODEL")
        table.add_column("ENDPOINT")
        table.add_column("STATUS")

        for s in services:
            table.add_row(
                s["deployment_id"],
                s.get("model_id", "-"),
                s.get("endpoint", "-"),
                s["status"],
            )

        console.print(table)

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())