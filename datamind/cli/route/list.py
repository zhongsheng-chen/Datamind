"""列出路由命令

提供路由规则列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_routes: 列出路由规则

使用示例：
  python -m datamind.cli.main route list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.config import get_service_config
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="列出路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_routes(
        name: str | None = typer.Option(
            None,
            "--name",
            help="按路由名称过滤",
        ),
        deployment_id: str | None = typer.Option(
            None,
            "--deployment-id",
            help="按部署 ID 过滤"
        ),
        rollout: str | None = typer.Option(
            None,
            "--rollout",
            help="按发布方式过滤，可选值：full / canary / shadow"
        ),
        rollout_group: str | None = typer.Option(
            None,
            "--group",
            "--rollout-group",
            help="按发布分组过滤，可选值：champion / challenger"
        ),
        enabled: bool | None = typer.Option(
            None,
            "--enabled/--disabled",
            help="按是否启用过滤"
        ),
        created_by: str | None = typer.Option(
            None,
            "--created-by",
            help="按创建人过滤"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除路由",
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
    """列出路由规则"""
    environment = get_service_config().environment

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        logger.info(
            "开始列出路由",
            name=name,
            deployment_id=deployment_id,
            environment=environment,
            rollout_type=rollout,
            rollout_group=rollout_group,
            enabled=enabled,
            created_by=created_by,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            routing_repo = RoutingRepository(
                uow.session
            )
            deployment_repo = DeploymentRepository(
                uow.session
            )

            routes = await routing_repo.list_routings(
                name=name,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
                deployment_id=deployment_id,
                environment=environment,
                rollout_type=rollout,
                rollout_group=rollout_group,
                enabled=enabled,
                created_by=created_by,
            )

            result = []

            for route in routes:
                deployment = await deployment_repo.get_deployment(
                    route.deployment_id,
                    include_deleted=True,
                )
                result.append({
                    "routing_id": route.routing_id,
                    "name": route.name,
                    "deployment_id": route.deployment_id,
                    "environment": (
                        deployment.environment
                        if deployment is not None
                        else route.environment
                    ),
                    "rollout_type": (
                        deployment.rollout_type
                        if deployment is not None
                        else route.rollout_type
                    ),
                    "rollout_group": (
                        deployment.role
                        if deployment is not None
                        else route.rollout_group
                    ),
                    "enabled": route.enabled,
                    "traffic_ratio": route.traffic_ratio,
                    "rules": route.rules,
                    "description": route.description,
                    "created_by": route.created_by,
                    "updated_by": route.updated_by,
                    "created_at": format_iso_utc(route.created_at),
                    "updated_at": format_iso_utc(route.updated_at),
                    "deleted_at": format_iso_utc(route.deleted_at),
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
                "路由列表输出完成",
                count=len(result),
                output=output,
            )

            return result

        console.print(f"[dim]共找到 {len(result)} 条路由[/dim]\n")

        if not result:
            logger.info(
                "路由列表为空",
                count=0,
            )
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("ROUTE NAME")
        table.add_column("ROUTING ID")
        table.add_column("DEPLOYMENT ID")
        table.add_column("ROLLOUT TYPE")
        table.add_column("GROUP")
        table.add_column("TRAFFIC RATIO")
        table.add_column("ENABLED")
        table.add_column("UPDATED AT")

        if include_deleted:
            table.add_column("DELETED AT")

        for item in result:
            row = [
                item["name"],
                item["routing_id"],
                item["deployment_id"],
                item["rollout_type"],
                item["rollout_group"] or "-",
                str(item["traffic_ratio"]),
                str(item["enabled"]),
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
            "路由列表输出完成",
            count=len(result),
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="routing.read",
        ):
            await _run()

    asyncio.run(runner())
