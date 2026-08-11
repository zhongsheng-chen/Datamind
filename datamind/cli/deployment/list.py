# datamind/cli/deployment/list.py

"""列出部署命令

提供部署的列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_deployments: 列出部署

使用示例：
  python -m datamind.cli.main deployment list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.repositories.deployment import DeploymentRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="列出部署命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_deployments(
        model_id: str | None = typer.Option(
            None,
            "--model-id",
            help="按模型 ID 过滤"
        ),
        version_id: str | None = typer.Option(
            None,
            "--version-id",
            help="按版本 ID 过滤"
        ),
        framework: str | None = typer.Option(
            None,
            "--framework",
            help="按模型框架过滤，可选值：sklearn / xgboost / lightgbm / catboost"
        ),
        rollout: str | None = typer.Option(
            None,
            "--rollout",
            help="按发布方式过滤，可选值：full / canary / shadow"
        ),
        role: str | None = typer.Option(
            None,
            "--role",
            help="按部署角色过滤，可选值：champion / challenger"
        ),
        status: str | None = typer.Option(
            None,
            "--status",
            help="按部署状态过滤，可选值：active / inactive"
        ),
        deployed_by: str | None = typer.Option(
            None,
            "--deployed-by",
            help="按部署人过滤"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除部署",
        ),
        limit: int = typer.Option(
            10,
            "--limit",
            help="返回记录数量限制"
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            help="分页偏移量"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """列出部署"""
    environment = str(get_settings().service.environment)

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {"environment": environment}

        if model_id is not None:
            filters["model_id"] = model_id

        if version_id is not None:
            filters["version_id"] = version_id

        if framework is not None:
            filters["framework"] = framework

        if rollout is not None:
            filters["rollout_type"] = rollout

        if role is not None:
            filters["role"] = role

        if status is not None:
            filters["status"] = status

        if deployed_by is not None:
            filters["deployed_by"] = deployed_by

        logger.info(
            "开始列出部署",
            filters=filters,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployments = await repo.list_deployments(
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
                **filters,
            )

            result = []

            for deployment in deployments:
                result.append({
                    "deployment_id": deployment.deployment_id,
                    "model_id": deployment.model_id,
                    "version_id": deployment.version_id,
                    "framework": deployment.framework,
                    "environment": deployment.environment,
                    "rollout_type": deployment.rollout_type,
                    "role": deployment.role,
                    "status": deployment.status,
                    "deployed_by": deployment.deployed_by,
                    "created_at": format_iso_utc(deployment.created_at),
                    "updated_at": format_iso_utc(deployment.updated_at),
                    "deleted_at": format_iso_utc(deployment.deleted_at),
                })

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            logger.info(
                "部署列表输出完成",
                count=len(result),
                output=output,
            )
            return result

        console.print(f"[dim]共找到 {len(result)} 个部署[/dim]\n")

        if not result:
            logger.info(
                "部署列表为空",
                count=0,
            )
            return result

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

        if include_deleted:
            table.add_column("DELETED AT")

        for item in result:
            row = [
                item["deployment_id"],
                item["model_id"],
                item["version_id"],
                item["framework"],
                item["environment"],
                item["rollout_type"],
                item["role"],
                item["status"],
                format_datetime(parse_datetime(item["updated_at"])),
            ]

            if include_deleted:
                row.append(
                    format_datetime(
                        parse_datetime(item["deleted_at"])
                    ) or "-"
                )

            table.add_row(*row)

        console.print(table)

        logger.info(
            "部署列表输出完成",
            count=len(result),
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.read",
        ):
            await _run()

    asyncio.run(runner())
