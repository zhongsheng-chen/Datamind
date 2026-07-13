# datamind/cli/route/show.py

"""查看路由命令

提供单条路由规则详情查询功能。

核心功能：
  - show_route: 查看路由规则详情

使用示例：
  python -m datamind.cli.main route show rtn_a1b2c3d4
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import RoutingRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="查看路由命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
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
    """查看路由规则详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看路由详情",
            routing_id=routing_id,
        )

        async with UnitOfWork() as uow:
            repo = RoutingRepository(
                uow.session
            )

            route = await repo.get_routing(
                routing_id
            )

        if route is None:
            console.print(
                f"[red]路由不存在: {routing_id}[/red]"
            )
            raise typer.Exit(1)

        result = {
            "routing_id": route.routing_id,
            "deployment_id": route.deployment_id,
            "environment": route.environment,
            "rollout_type": route.rollout_type,
            "rollout_group": route.rollout_group,
            "enabled": route.enabled,
            "traffic_ratio": route.traffic_ratio,
            "rules": route.rules,
            "description": route.description,
            "created_by": route.created_by,
            "updated_by": route.updated_by,
            "created_at": format_iso_utc(route.created_at),
            "updated_at": format_iso_utc(route.updated_at),
        }

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

            logger.info(
                "路由详情输出完成",
                routing_id=routing_id,
                output=output,
            )

            return result

        console.print("[green]路由详情[/green]\n")

        console.print(f"[cyan]{'ROUTING ID':<16}[/cyan] : {result['routing_id']}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(f"[cyan]{'ROLLOUT GROUP':<16}[/cyan] : {result['rollout_group'] or '-'}")
        console.print(f"[cyan]{'ENABLED':<16}[/cyan] : {result['enabled']}")
        console.print(f"[cyan]{'TRAFFIC':<16}[/cyan] : {result['traffic_ratio']}")

        if result["rules"]:
            console.print(
                f"[cyan]{'RULES':<16}[/cyan] : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        console.print(f"[cyan]{'DESCRIPTION':<16}[/cyan] : {result['description'] or '-'}")
        console.print(f"[cyan]{'CREATED BY':<16}[/cyan] : {result['created_by'] or '-'}")
        console.print(f"[cyan]{'UPDATED BY':<16}[/cyan] : {result['updated_by'] or '-'}")
        console.print(f"[cyan]{'CREATED AT':<16}[/cyan] : {format_datetime(route.created_at)}")
        console.print(f"[cyan]{'UPDATED AT':<16}[/cyan] : {format_datetime(route.updated_at)}")

        logger.info(
            "路由详情输出完成",
            routing_id=routing_id,
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                verbose=verbose,
                enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())
