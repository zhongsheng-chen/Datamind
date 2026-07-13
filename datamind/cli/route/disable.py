# datamind/cli/route/disable.py

"""禁用路由命令

提供路由规则禁用功能。

核心功能：
  - disable_route: 禁用路由规则

使用示例：
  python -m datamind.cli.main route disable rtn_a1b2c3d4 --operator admin
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import RoutingRepository
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="禁用路由命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("disable")
def disable_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
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
    """禁用路由规则"""

    @audit(
        action="route.disable",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始禁用路由",
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

            repo.disable_routing(
                route,
                updated_by=operator,
            )

            await uow.session.flush()
            await uow.session.refresh(route)

            result = {
                "routing_id": route.routing_id,
                "deployment_id": route.deployment_id,
                "environment": route.environment,
                "rollout_type": route.rollout_type,
                "rollout_group": route.rollout_group,
                "enabled": route.enabled,
                "traffic_ratio": route.traffic_ratio,
                "updated_by": route.updated_by,
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
            return result

        console.print("[green]路由禁用成功[/green]\n")

        console.print(f"[cyan]{'ROUTING ID':<16}[/cyan] : {result['routing_id']}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(f"[cyan]{'ROLLOUT GROUP':<16}[/cyan] : {result['rollout_group'] or '-'}")
        console.print(f"[cyan]{'TRAFFIC':<16}[/cyan] : {result['traffic_ratio']}")
        console.print(f"[cyan]{'ENABLED':<16}[/cyan] : {result['enabled']}")

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
