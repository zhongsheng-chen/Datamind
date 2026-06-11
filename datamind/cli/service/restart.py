# datamind/cli/service/restart.py

"""重启服务命令"""

import asyncio
import typer
import structlog
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="重启服务")
console = Console()
logger = structlog.get_logger(__name__)


@app.command("restart")
def restart_service(
    deployment_id: str = typer.Argument(..., help="部署 ID"),
    operator: str = typer.Option("system", "--operator", help="操作人"),
    verbose: bool = typer.Option(False, "--verbose", help="调试模式"),
):
    """重启服务"""

    async def _run():
        logger.info("重启服务", deployment_id=deployment_id)

        manager = RuntimeManager()

        result = await manager.restart(
            deployment_id=deployment_id,
            operator=operator,
        )

        console.print("[green]服务重启成功[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'ENDPOINT':<16}[/cyan] : {result['endpoint']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())