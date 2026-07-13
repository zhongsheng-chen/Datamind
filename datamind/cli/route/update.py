# datamind/cli/route/update.py

"""更新路由命令

提供路由规则更新功能。

核心功能：
  - update_route: 更新路由规则

使用示例：
  python -m datamind.cli.main route update rtn_a1b2c3d4 --traffic 0.3 --operator admin
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingPatch,
    RoutingRepository,
)
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="更新路由命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("update")
def update_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
        ),
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="路由环境，例如 production/staging/development/testing"
        ),
        traffic: float | None = typer.Option(
            None,
            "--traffic",
            help="路由权重，范围 0~1"
        ),
        rollout: str | None = typer.Option(
            None,
            "--rollout",
            help="发布方式 full/canary/shadow"
        ),
        rollout_group: str | None = typer.Option(
            None,
            "--group",
            "--rollout-group",
            help="发布分组，例如 champion/challenger"
        ),
        rules: str | None = typer.Option(
            None,
            "--rules",
            help="路由规则 JSON 字符串"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="路由描述"
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
    """更新路由规则"""

    @audit(
        action="route.update",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if traffic is not None and (
                traffic < 0 or traffic > 1
        ):
            raise typer.BadParameter(
                "--traffic 必须在 0 到 1 之间"
            )

        route_rules = None

        if rules:
            try:
                route_rules = json.loads(
                    rules
                )

            except json.JSONDecodeError as exc:
                console.print(
                    "[red]rules JSON 解析失败: "
                    f"{exc}[/red]"
                )
                raise typer.Exit(1)

            if not isinstance(
                    route_rules,
                    dict,
            ):
                raise typer.BadParameter(
                    "--rules 必须是 JSON 对象"
                )

        if (
                environment is None
                and traffic is None
                and rollout is None
                and rollout_group is None
                and rules is None
                and description is None
        ):
            raise typer.BadParameter(
                "至少需要提供一个更新参数"
            )

        logger.info(
            "开始更新路由",
            routing_id=routing_id,
            environment=environment,
            traffic=traffic,
            rollout=rollout,
            rollout_group=rollout_group,
        )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )

            routing_repo = RoutingRepository(
                uow.session
            )

            route = await routing_repo.get_routing(
                routing_id
            )

            if route is None:
                console.print(
                    f"[red]路由不存在: {routing_id}[/red]"
                )
                raise typer.Exit(1)

            deployment = await deployment_repo.get_deployment(
                route.deployment_id
            )

            if deployment is None:
                console.print(
                    "[red]路由关联的部署不存在: "
                    f"{route.deployment_id}[/red]"
                )
                raise typer.Exit(1)

            resolved_environment = (
                environment
                if environment is not None
                else route.environment
            )

            if deployment.environment != resolved_environment:
                console.print(
                    "[red]路由环境与部署环境不一致[/red]\n"
                    f"部署环境: {deployment.environment}\n"
                    f"路由环境: {resolved_environment}"
                )
                raise typer.Exit(1)

            patch = RoutingPatch(
                rollout_type=rollout,
                rollout_group=rollout_group,
                environment=environment,
                traffic_ratio=traffic,
                rules=route_rules,
                description=description,
            )

            try:
                routing_repo.update_routing(
                    route,
                    patch,
                    updated_by=operator,
                )

            except ValueError as exc:
                console.print(
                    f"[red]{exc}[/red]"
                )
                raise typer.Exit(1)

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
                "rules": route.rules,
                "description": route.description,
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

        console.print("[green]路由更新成功[/green]\n")

        console.print(f"[cyan]{'ROUTING ID':<16}[/cyan] : {result['routing_id']}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(f"[cyan]{'ROLLOUT GROUP':<16}[/cyan] : {result['rollout_group'] or '-'}")
        console.print(f"[cyan]{'TRAFFIC':<16}[/cyan] : {result['traffic_ratio']}")
        console.print(f"[cyan]{'ENABLED':<16}[/cyan] : {result['enabled']}")

        if result["rules"]:
            console.print(
                f"[cyan]{'RULES':<16}[/cyan] : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        console.print(f"[cyan]{'DESCRIPTION':<16}[/cyan] : {result['description'] or '-'}")
        console.print(f"[cyan]{'UPDATED BY':<16}[/cyan] : {result['updated_by'] or '-'}")
        console.print(f"[cyan]{'UPDATED AT':<16}[/cyan] : {format_datetime(result['updated_at'])}")

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
