# datamind/cli/deployment/show.py

"""部署详情命令

提供单个部署的详细信息查询功能。

核心功能：
  - show_deployment: 查看部署详情

使用示例：
  python -m datamind.cli.main deployment show dep_a1b2c3d4
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories.deployment import DeploymentRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="部署详情命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_deployment(
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
            help="是否输出调试日志"
        ),
):
    """查看部署详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查询部署详情",
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(deployment_id)

        if not deployment:
            console.print(f"[red]未找到部署: {deployment_id}[/red]")
            raise typer.Exit(1)

        if output == "json":
            result = {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "framework": deployment.framework,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
                "config": deployment.config,
                "description": deployment.description,
                "deployed_by": deployment.deployed_by,
                "effective_from": format_iso_utc(deployment.effective_from),
                "effective_to": format_iso_utc(deployment.effective_to),
                "created_at": format_iso_utc(deployment.created_at),
                "updated_at": format_iso_utc(deployment.updated_at),
            }

            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

            logger.info(
                "部署详情输出完成",
                deployment_id=deployment_id,
                output=output,
            )
            return result

        console.print("[green]部署详情[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {deployment.deployment_id}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {deployment.model_id}")
        console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {deployment.version_id}")
        console.print(f"[cyan]{'FRAMEWORK':<16}[/cyan] : {deployment.framework}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {deployment.environment}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {deployment.rollout_type}")
        console.print(f"[cyan]{'ROLE':<16}[/cyan] : {deployment.role}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {deployment.status}")

        if deployment.config:
            console.print(
                f"[cyan]{'CONFIG':<16}[/cyan] : "
                f"{json.dumps(deployment.config, ensure_ascii=False)}"
            )

        console.print(f"[cyan]{'DESCRIPTION':<16}[/cyan] : {deployment.description or '-'}")
        console.print(f"[cyan]{'DEPLOYED BY':<16}[/cyan] : {deployment.deployed_by or '-'}")
        console.print(f"[cyan]{'CREATED AT':<16}[/cyan] : {format_datetime(deployment.created_at)}")
        console.print(f"[cyan]{'UPDATED AT':<16}[/cyan] : {format_datetime(deployment.updated_at)}")

        if deployment.effective_from:
            console.print(
                f"[cyan]{'EFFECTIVE FROM':<16}[/cyan] : "
                f"{format_datetime(deployment.effective_from)}"
            )

        if deployment.effective_to:
            console.print(
                f"[cyan]{'EFFECTIVE TO':<16}[/cyan] : "
                f"{format_datetime(deployment.effective_to)}"
            )

        logger.info(
            "部署详情输出完成",
            deployment_id=deployment_id,
            output=output,
        )

        return deployment

    async def runner():
        async with cli_context(
                verbose=verbose,
                enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())
