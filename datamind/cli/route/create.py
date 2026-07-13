# datamind/cli/route/create.py

"""创建路由命令

提供模型路由规则创建功能。

核心功能：
  - create_route: 创建路由规则

使用示例：
  python -m datamind.cli.main route create dep_0123456789abcdef \
    --environment development \
    --traffic-ratio 0.8 \
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
from datamind.config import get_settings
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.runtime.routing import RuleMatcher
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="创建路由命令")
console = Console()

logger = structlog.get_logger(__name__)

CHAMPION_ROLE = "champion"
CHAMPION_TRAFFIC_RATIO_WARN_THRESHOLD = 0.7


@app.command("create")
def create_route(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="路由环境，默认使用服务配置"
        ),
        traffic_ratio: float = typer.Option(
            ...,
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
        enabled: bool = typer.Option(
            True,
            "--enabled/--disabled",
            help="是否启用路由"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """创建路由规则"""
    settings = get_settings()
    service_config = settings.service

    environment_value = (
        environment
        if environment is not None
        else str(
            service_config.environment
        )
    )

    try:
        resolved_environment = Environment(
            environment_value
        )
    except ValueError as exc:
        raise typer.BadParameter(
            f"不支持的路由环境: {environment_value}"
        ) from exc

    @audit(
        action="route.create",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if traffic_ratio < 0 or traffic_ratio > 1:
            raise typer.BadParameter(
                "--traffic-ratio 必须在 0 到 1 之间"
            )

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

            except json.JSONDecodeError as json_error:
                console.print(
                    "[red]rules-file JSON 解析失败: "
                    f"{json_error}[/red]"
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

            except ValueError as validation_error:
                console.print(
                    "[red]rules 规则校验失败: "
                    f"{validation_error}[/red]"
                )
                raise typer.Exit(1)

        logger.info(
            "开始创建路由",
            deployment_id=deployment_id,
            environment=resolved_environment,
            traffic_ratio=traffic_ratio,
            rules_file=rules_file,
            enabled=enabled,
        )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )

            routing_repo = RoutingRepository(
                uow.session
            )

            deployment = await deployment_repo.get_deployment(
                deployment_id
            )

            if deployment is None:
                console.print(
                    f"[red]部署不存在: {deployment_id}[/red]"
                )
                raise typer.Exit(1)

            if deployment.environment != resolved_environment:
                console.print(
                    "[red]路由环境与部署环境不一致[/red]\n"
                    f"部署环境: {deployment.environment}\n"
                    f"路由环境: {resolved_environment}"
                )
                raise typer.Exit(1)

            if (
                    str(deployment.role).lower() == CHAMPION_ROLE
                    and traffic_ratio < CHAMPION_TRAFFIC_RATIO_WARN_THRESHOLD
            ):
                if output == "text":
                    console.print(
                        "[yellow]警告: champion 路由流量比例低于 0.7，"
                        "请确认是否符合预期[/yellow]"
                    )

                logger.warning(
                    "champion 路由流量比例低于建议值",
                    deployment_id=deployment.deployment_id,
                    role=deployment.role,
                    traffic_ratio=traffic_ratio,
                    warning_threshold=CHAMPION_TRAFFIC_RATIO_WARN_THRESHOLD,
                )

            route = routing_repo.create_routing(
                routing_id=generate_random_id(
                    prefix="rtn"
                ),
                deployment_id=deployment_id,
                environment=resolved_environment,
                rollout_type=deployment.rollout_type,
                rollout_group=deployment.role,
                traffic_ratio=traffic_ratio,
                enabled=enabled,
                rules=route_rules,
                description=description,
                created_by=actor,
            )

            result: dict[str, Any] = {
                "routing_id": route.routing_id,
                "deployment_id": route.deployment_id,
                "environment": route.environment,
                "rollout_type": route.rollout_type,
                "rollout_group": route.rollout_group,
                "traffic_ratio": route.traffic_ratio,
                "enabled": route.enabled,
                "rules": route.rules,
                "description": route.description,
                "created_by": route.created_by,
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

        console.print(
            "[green]路由创建成功[/green]\n"
        )

        console.print(
            f"[cyan]{'ROUTING ID':<16}[/cyan] : "
            f"{result['routing_id']}"
        )
        console.print(
            f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : "
            f"{result['deployment_id']}"
        )
        console.print(
            f"[cyan]{'ENVIRONMENT':<16}[/cyan] : "
            f"{result['environment']}"
        )
        console.print(
            f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : "
            f"{result['rollout_type']}"
        )
        console.print(
            f"[cyan]{'ROLLOUT GROUP':<16}[/cyan] : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(
            f"[cyan]{'TRAFFIC RATIO':<16}[/cyan] : "
            f"{result['traffic_ratio']}"
        )
        console.print(
            f"[cyan]{'ENABLED':<16}[/cyan] : "
            f"{result['enabled']}"
        )

        if result["rules"]:
            console.print(
                f"[cyan]{'RULES':<16}[/cyan] : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        console.print(
            f"[cyan]{'DESCRIPTION':<16}[/cyan] : "
            f"{result['description'] or '-'}"
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
