# datamind/cli/deployment/show.py

"""部署详情命令

提供单个部署的详细信息查询功能。

核心功能：
  - show_deployment: 查看部署详情

使用示例：
  python -m datamind.cli.main deployment show dep_0123456789abcdef
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories.deployment import DeploymentRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

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
            help="输出格式：text / json"
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

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            logger.info(
                "部署详情输出完成",
                deployment_id=deployment_id,
                output=output,
            )
            return result

        console.print("[green]部署详情[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'FRAMEWORK':<16}[/cyan] : {result['framework']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(f"[cyan]{'ROLE':<16}[/cyan] : {result['role']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        if result["config"]:
            console.print(
                f"[cyan]{'CONFIG':<16}[/cyan] : "
                f"{json.dumps(result['config'], ensure_ascii=False)}"
            )

        console.print(
            f"[cyan]{'DESCRIPTION':<16}[/cyan] : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"[cyan]{'DEPLOYED BY':<16}[/cyan] : "
            f"{result['deployed_by'] or '-'}"
        )
        console.print(
            f"[cyan]{'CREATED AT':<16}[/cyan] : "
            f"{format_datetime(parse_datetime(result['created_at']))}"
        )
        console.print(
            f"[cyan]{'UPDATED AT':<16}[/cyan] : "
            f"{format_datetime(parse_datetime(result['updated_at']))}"
        )

        if result["effective_from"]:
            console.print(
                f"[cyan]{'EFFECTIVE FROM':<16}[/cyan] : "
                f"{format_datetime(parse_datetime(result['effective_from']))}"
            )

        if result["effective_to"]:
            console.print(
                f"[cyan]{'EFFECTIVE TO':<16}[/cyan] : "
                f"{format_datetime(parse_datetime(result['effective_to']))}"
            )

        logger.info(
            "部署详情输出完成",
            deployment_id=deployment_id,
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.read",
        ):
            await _run()

    asyncio.run(runner())
