# datamind/cli/route/update.py

"""更新路由命令

提供路由规则更新功能。

核心功能：
  - update_route: 更新路由规则

使用示例：
  python -m datamind.cli.main route update rtn_0123456789abcdef \
    --traffic-ratio 0.3 \
    --rules-file route_rules.json
"""

import asyncio
import json
from typing import Any

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingPatch,
    RoutingRepository,
)
from datamind.runtime.routing import RuleMatcher
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="更新路由命令")
console = Console()

logger = structlog.get_logger(__name__)

CHAMPION_ROLE = "champion"
CHAMPION_TRAFFIC_WARN_THRESHOLD = 0.7


@app.command("update")
def update_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
        ),
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="路由环境，可选值：production / staging / development / testing"
        ),
        traffic_ratio: float | None = typer.Option(
            None,
            "--traffic-ratio",
            help="路由流量比例，范围 0~1"
        ),
        rules_file: str | None = typer.Option(
            None,
            "--rules-file",
            help="路由规则文件(JSON)"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="路由描述"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """更新路由规则"""

    @audit(
        action="route.update",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if traffic_ratio is not None and (
                traffic_ratio < 0 or traffic_ratio > 1
        ):
            raise typer.BadParameter(
                "--traffic-ratio 必须在 0 到 1 之间"
            )

        requested_environment: Environment | None = None

        if environment is not None:
            try:
                requested_environment = Environment(
                    environment
                )
            except ValueError as exc:
                raise typer.BadParameter(
                    f"不支持的路由环境: {environment}"
                ) from exc

        route_rules = None

        if rules_file:
            logger.debug(
                "读取路由规则文件",
                rules_file=rules_file,
            )

            try:
                with open(
                        rules_file,
                        "r",
                        encoding="utf-8",
                ) as f:
                    route_rules = json.load(f)

                logger.debug(
                    "路由规则文件解析成功",
                    rules=route_rules,
                )

            except FileNotFoundError:
                console.print(
                    "[red]rules 文件不存在: "
                    f"{rules_file}[/red]"
                )
                raise typer.Exit(1)

            except json.JSONDecodeError as exc:
                console.print(
                    "[red]rules-file JSON 解析失败: "
                    f"{exc}[/red]"
                )
                raise typer.Exit(1)

            if not isinstance(
                    route_rules,
                    dict,
            ):
                raise typer.BadParameter(
                    "--rules-file 必须是 JSON 对象"
                )

            try:
                RuleMatcher().validate(
                    route_rules
                )

            except ValueError as exc:
                console.print(
                    "[red]rules 规则校验失败: "
                    f"{exc}[/red]"
                )
                raise typer.Exit(1)

        if (
                environment is None
                and traffic_ratio is None
                and rules_file is None
                and description is None
        ):
            raise typer.BadParameter(
                "至少需要提供一个更新参数"
            )

        logger.info(
            "开始更新路由",
            routing_id=routing_id,
            environment=requested_environment,
            traffic_ratio=traffic_ratio,
            rules_file=rules_file,
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
                requested_environment
                if requested_environment is not None
                else Environment(
                    route.environment
                )
            )

            if deployment.environment != resolved_environment:
                console.print(
                    "[red]路由环境与部署环境不一致[/red]\n"
                    f"部署环境: {deployment.environment}\n"
                    f"路由环境: {resolved_environment}"
                )
                raise typer.Exit(1)

            target_traffic_ratio = (
                traffic_ratio
                if traffic_ratio is not None
                else route.traffic_ratio
            )

            if (
                    str(deployment.role).lower() == CHAMPION_ROLE
                    and target_traffic_ratio < CHAMPION_TRAFFIC_WARN_THRESHOLD
            ):
                if output == "text":
                    console.print(
                        "[yellow]警告: champion 路由流量比例低于建议值，"
                        "请确认是否符合预期[/yellow]"
                    )

                logger.warning(
                    "champion 路由流量比例低于建议值",
                    routing_id=route.routing_id,
                    deployment_id=deployment.deployment_id,
                    role=deployment.role,
                    traffic_ratio=target_traffic_ratio,
                    warning_threshold=CHAMPION_TRAFFIC_WARN_THRESHOLD,
                )

            patch = RoutingPatch(
                rollout_type=deployment.rollout_type,
                rollout_group=deployment.role,
                environment=requested_environment,
                traffic_ratio=traffic_ratio,
                rules=route_rules,
                description=description,
            )

            try:
                routing_repo.update_routing(
                    route,
                    patch,
                    updated_by=actor,
                )

            except ValueError as exc:
                console.print(
                    f"[red]{exc}[/red]"
                )
                raise typer.Exit(1)

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
                )
            )
            return result

        console.print("[green]路由更新成功[/green]\n")

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

        if result["rules"]:
            console.print(
                f"[cyan]{'RULES':<16}[/cyan] : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        console.print(
            f"[cyan]{'DESCRIPTION':<16}[/cyan] : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"[cyan]{'UPDATED BY':<16}[/cyan] : "
            f"{result['updated_by'] or '-'}"
        )
        console.print(
            f"[cyan]{'UPDATED AT':<16}[/cyan] : "
            f"{format_datetime(parse_datetime(result['updated_at']))}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="routing.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
