# datamind/cli/route/enable.py

"""启用路由命令

提供路由规则启用功能。

核心功能：
  - enable_route: 启用路由规则

使用示例：
  python -m datamind.cli.main route enable rtn_0123456789abcdef
"""

import asyncio
import json
from typing import Any

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import RoutingRepository
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="启用路由命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("enable")
def enable_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """启用路由规则"""

    @audit(
        action="route.enable",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始启用路由",
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

            repo.enable_routing(
                route,
                updated_by=actor,
            )

            await uow.session.flush()
            await uow.session.refresh(route)

            result: dict[str, Any] = {
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
                )
            )
            return result

        console.print("[green]路由启用成功[/green]\n")

        console.print(f"[cyan]{'ROUTING ID':<16}[/cyan] : {result['routing_id']}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(
            f"[cyan]{'ROLLOUT GROUP':<16}[/cyan] : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(f"[cyan]{'TRAFFIC RATIO':<16}[/cyan] : {result['traffic_ratio']}")
        console.print(f"[cyan]{'ENABLED':<16}[/cyan] : {result['enabled']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="routing.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
