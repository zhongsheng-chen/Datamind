# datamind/cli/deployment/enable.py

"""启用部署命令

提供部署启用功能。

核心功能：
  - enable_deployment: 启用部署

使用示例：
  python -m datamind.cli.main deployment enable dep_0123456789abcdef
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services import DeploymentLifecycleService

app = typer.Typer(help="启用部署命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("enable")
def enable_deployment(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """启用部署"""

    @audit(
        action="deploy.enable",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始启用部署",
            deployment_id=deployment_id,
        )

        deployer = DeploymentLifecycleService()

        result = await deployer.enable_deployment(
            deployment_id=deployment_id,
            updated_by=actor,
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

        console.print("[green]部署启用成功[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
