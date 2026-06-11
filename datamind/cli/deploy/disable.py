# datamind/cli/deploy/disable.py

"""禁用部署命令

提供部署禁用功能。

核心功能：
  - disable_deployment: 禁用部署

使用示例：
  python -m datamind.cli.main deploy disable dep_a1b2c3d4
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services.deployer import ModelDeployer

app = typer.Typer(help="禁用部署命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("disable")
def disable_deployment(
    deployment_id: str = typer.Argument(
        ...,
        help="部署 ID"
    ),
    operator: str = typer.Option(
        "system",
        "--operator",
        help="操作人"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="是否输出调试日志"
    ),
):
    """禁用部署"""

    @audit(
        action="deploy.disable",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run():
        logger.info(
            "开始禁用部署",
            deployment_id=deployment_id,
        )

        deployer = ModelDeployer()

        result = await deployer.disable_deployment(
            deployment_id=deployment_id,
            updated_by=operator,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.print("[green]部署禁用成功[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
            user=operator,
            source="cli",
            verbose=verbose,
            enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())