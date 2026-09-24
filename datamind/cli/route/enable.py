"""启用路由命令.

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

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.utils.datetime import format_iso_utc
from datamind.services.routing import validate_routing_allocation

app = typer.Typer(help="启用路由命令")
console = CLIConsole()

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
    """启用路由规则."""

    @audit(
        action="route.enable",
        target_type="routing",
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
            routing_repo = RoutingRepository(
                uow.session
            )
            deployment_repo = DeploymentRepository(
                uow.session
            )

            route = await routing_repo.get_routing(
                routing_id
            )

            if route is None:
                console.error(
                    f"启用路由失败：路由不存在：{routing_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            deployment = await deployment_repo.get_deployment(
                route.deployment_id
            )

            if deployment is None:
                console.error(
                    "启用路由失败：关联部署不存在："
                    f"{route.deployment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                await validate_routing_allocation(
                    routing_repo=routing_repo,
                    deployment_repo=deployment_repo,
                    deployment=deployment,
                    traffic_ratio=route.traffic_ratio,
                    exclude_routing_id=route.routing_id,
                )
                routing_repo.enable_routing(
                    route,
                    updated_by=actor,
                )
            except ValueError as error:
                console.error(
                    f"启用路由失败：{error}",
                    output_format=output,
                    error_type=type(error).__name__,
                )
                raise typer.Exit(code=1) from None

            await uow.session.flush()
            await uow.session.refresh(route)

            result: dict[str, Any] = {
                "routing_id": route.routing_id,
                "deployment_id": route.deployment_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "rollout_group": deployment.role,
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

        console.info("路由启用成功\n")

        console.print(f"{'ROUTING ID':<16} : {result['routing_id']}")
        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'ROLLOUT TYPE':<16} : {result['rollout_type']}")
        console.print(
            f"{'ROLLOUT GROUP':<16} : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(f"{'TRAFFIC RATIO':<16} : {result['traffic_ratio']}")
        console.print(f"{'ENABLED':<16} : {result['enabled']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="routing.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
