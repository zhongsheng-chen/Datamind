# datamind/cli/deploy/list.py

"""列出部署命令

提供部署的列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_deployments: 列出部署

使用示例：
  python -m datamind.cli.main deploy list
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

app = typer.Typer(help="列出部署命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_deployments(
    framework: str | None = typer.Option(
        None,
        "--framework",
        help="框架类型"
    ),
    environment: str | None = typer.Option(
        None,
        "--environment",
        help="部署环境"
    ),
    rollout: str | None = typer.Option(
        None,
        "--rollout",
        help="发布方式（full / canary / shadow）"
    ),
    role: str | None = typer.Option(
        None,
        "--role",
        help="部署角色（champion / challenger）"
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="部署状态"
    ),
    deployed_by: str | None = typer.Option(
        None,
        "--deployed-by",
        help="部署人"
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        help="返回数量"
    ),
    offset: int = typer.Option(
        0,
        "--offset",
        help="分页偏移"
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
    """列出部署"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {
            "framework": framework,
            "environment": environment,
            "rollout_type": rollout,
            "role": role,
            "status": status,
            "deployed_by": deployed_by,
        }

        filters = {k: v for k, v in filters.items() if v is not None}

        logger.info(
            "开始列出部署",
            filters=filters,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployments = await repo.list_deployments(
                limit=limit,
                offset=offset,
                **filters,
            )

        if output == "json":
            result = []

            for d in deployments:
                result.append({
                    "deployment_id": d.deployment_id,
                    "model_id": d.model_id,
                    "version_id": d.version_id,
                    "framework": d.framework,
                    "environment": d.environment,
                    "rollout_type": d.rollout_type,
                    "role": d.role,
                    "status": d.status,
                    "deployed_by": d.deployed_by,
                    "created_at": format_iso_utc(d.created_at),
                    "updated_at": format_iso_utc(d.updated_at),
                })

            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            logger.info(
                "部署列表输出完成",
                count=len(deployments),
                output=output,
            )
            return

        console.print(f"[dim]共找到 {len(deployments)} 个部署[/dim]\n")

        if not deployments:
            logger.info(
                "部署列表为空",
                count=0,
            )
            return

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("DEPLOYMENT ID")
        table.add_column("MODEL ID")
        table.add_column("VERSION ID")
        table.add_column("FRAMEWORK")
        table.add_column("ENVIRONMENT")
        table.add_column("ROLLOUT TYPE")
        table.add_column("ROLE")
        table.add_column("STATUS")
        table.add_column("UPDATED AT")

        for d in deployments:
            table.add_row(
                d.deployment_id,
                d.model_id,
                d.version_id,
                d.framework,
                d.environment,
                d.rollout_type,
                d.role,
                d.status,
                format_datetime(d.updated_at),
            )

        console.print(table)

        logger.info(
            "部署列表输出完成",
            count=len(deployments),
            output=output,
        )

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())