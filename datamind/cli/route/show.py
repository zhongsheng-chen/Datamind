"""查看路由命令.

提供单条路由规则详情查询功能。

核心功能：
  - show_route: 查看路由规则详情

使用示例：
  python -m datamind.cli.main route show rtn_0123456789abcdef
"""

import asyncio
import json
from typing import Any

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="查看路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除路由",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """查看路由规则详情."""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看路由详情",
            routing_id=routing_id,
        )

        async with UnitOfWork() as uow:
            routing_repo = RoutingRepository(
                uow.session
            )
            deployment_repo = DeploymentRepository(
                uow.session
            )

            route = await routing_repo.get_routing(
                routing_id,
                include_deleted=include_deleted,
            )

            if route is None:
                console.error(
                    f"查看路由失败：路由不存在：{routing_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            deployment = await deployment_repo.get_deployment(
                route.deployment_id,
                include_deleted=True,
            )

            if deployment is None:
                console.error(
                    "查看路由失败：关联部署不存在："
                    f"{route.deployment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            result: dict[str, Any] = {
                "routing_id": route.routing_id,
                "name": route.name,
                "deployment_id": route.deployment_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "rollout_group": deployment.role,
                "enabled": route.enabled,
                "traffic_ratio": route.traffic_ratio,
                "rules": route.rules,
                "effective_from": format_iso_utc(
                    getattr(route, "effective_from", None)
                ),
                "effective_to": format_iso_utc(
                    getattr(route, "effective_to", None)
                ),
                "description": route.description,
                "created_by": route.created_by,
                "updated_by": route.updated_by,
                "created_at": format_iso_utc(route.created_at),
                "updated_at": format_iso_utc(route.updated_at),
                "deleted_at": format_iso_utc(route.deleted_at),
                "deleted_by": route.deleted_by,
                "deletion_reason": route.deletion_reason,
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
                "路由详情输出完成",
                routing_id=routing_id,
                output=output,
            )

            return result

        console.info("路由详情\n")

        console.print(f"{'ROUTE NAME':<16} : {result['name']}")
        console.print(f"{'ROUTING ID':<16} : {result['routing_id']}")
        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'ROLLOUT TYPE':<16} : {result['rollout_type']}")
        console.print(
            f"{'ROLLOUT GROUP':<16} : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(f"{'ENABLED':<16} : {result['enabled']}")
        console.print(f"{'TRAFFIC RATIO':<16} : {result['traffic_ratio']}")
        console.print(
            f"{'EFFECTIVE FROM':<16} : "
            f"{format_datetime(parse_datetime(result['effective_from']))}"
        )
        console.print(
            f"{'EFFECTIVE TO':<16} : "
            f"{format_datetime(parse_datetime(result['effective_to']))}"
        )

        if result["rules"]:
            console.print(
                f"{'RULES':<16} : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        console.print(
            f"{'DESCRIPTION':<16} : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"{'CREATED BY':<16} : "
            f"{result['created_by'] or '-'}"
        )
        console.print(
            f"{'UPDATED BY':<16} : "
            f"{result['updated_by'] or '-'}"
        )
        console.print(
            f"{'CREATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['created_at']))}"
        )
        console.print(
            f"{'UPDATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['updated_at']))}"
        )

        if result["deleted_at"]:
            console.print(
                f"{'DELETED AT':<16} : "
                f"{format_datetime(parse_datetime(result['deleted_at']))}"
            )
            console.print(
                f"{'DELETED BY':<16} : "
                f"{result['deleted_by'] or '-'}"
            )
            console.print(
                f"{'DELETE REASON':<16} : "
                f"{result['deletion_reason'] or '-'}"
            )

        logger.info(
            "路由详情输出完成",
            routing_id=routing_id,
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="routing.read",
        ):
            await _run()

    asyncio.run(runner())
