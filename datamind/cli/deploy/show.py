# datamind/cli/deploy/show.py

"""部署详情命令

提供单个部署的详细信息查询功能。

核心功能：
  - show_deployment: 查看部署详情

使用示例：
  python -m datamind.cli.main deploy show dep_a1b2c3d4
  python -m datamind.cli.main deploy show dep_a1b2c3d4 --format json
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console
from rich.table import Table
from rich import box

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
        "table",
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

        logger.info(
            "开始查询部署详情",
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(deployment_id)

        if not deployment:
            console.print(f"[red]未找到部署: {deployment_id}[/red]")
            return None

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
                "endpoint": deployment.endpoint,
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
                output="json",
            )
            return result

        console.print("\n[green]部署详情[/green]\n")

        table = Table(
            box=box.ASCII,
            show_header=False,
            pad_edge=False,
        )

        def add_row(key: str, value: str):
            table.add_row(f"[cyan]{key}[/cyan]", str(value))

        add_row("DEPLOYMENT ID", deployment.deployment_id)
        add_row("MODEL ID", deployment.model_id)
        add_row("VERSION ID", deployment.version_id)
        add_row("FRAMEWORK", deployment.framework)
        add_row("ENVIRONMENT", deployment.environment)
        add_row("ROLLOUT TYPE", deployment.rollout_type)
        add_row("ROLE", deployment.role)
        add_row("STATUS", deployment.status)

        if deployment.config:
            add_row("CONFIG", json.dumps(deployment.config, ensure_ascii=False))

        if deployment.endpoint:
            add_row("ENDPOINT", deployment.endpoint)

        if deployment.description:
            add_row("DESCRIPTION", deployment.description)

        if deployment.deployed_by:
            add_row("DEPLOYED BY", deployment.deployed_by)

        add_row("CREATED AT", format_datetime(deployment.created_at))
        add_row("UPDATED AT", format_datetime(deployment.updated_at))

        if deployment.effective_from:
            add_row("EFFECTIVE FROM", format_datetime(deployment.effective_from))

        if deployment.effective_to:
            add_row("EFFECTIVE TO", format_datetime(deployment.effective_to))

        console.print(table)

        logger.info(
            "部署详情输出完成",
            deployment_id=deployment_id,
            output="table",
        )

        return deployment

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())