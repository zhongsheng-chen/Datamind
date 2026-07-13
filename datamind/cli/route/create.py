# datamind/cli/route/create.py

"""创建路由命令

提供模型路由规则创建功能。

核心功能：
  - create_route: 创建路由规则

使用示例：
  python -m datamind.cli.main route create dep_a1b2c3d4 \
    --environment development \
    --traffic 0.8 \
    --rollout canary \
    --group champion \
    --rules "{\"bucket_key\": \"customer_id\"}" \
    --operator admin
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="创建路由命令")
console = Console()

logger = structlog.get_logger(__name__)


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
        traffic: float = typer.Option(
            ...,
            "--traffic",
            help="路由权重，范围 0~1"
        ),
        rollout: str | None = typer.Option(
            None,
            "--rollout",
            help="发布方式 full/canary/shadow，默认使用部署发布方式"
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
        enabled: bool = typer.Option(
            True,
            "--enabled/--disabled",
            help="是否启用路由"
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
    """创建路由规则"""
    settings = get_settings()
    service_config = settings.service

    resolved_environment = (
        environment
        if environment is not None
        else service_config.environment
    )

    @audit(
        action="route.create",
        target_type="route",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if not resolved_environment:
            raise typer.BadParameter(
                "--environment 不能为空"
            )

        if traffic < 0 or traffic > 1:
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

        logger.info(
            "开始创建路由",
            deployment_id=deployment_id,
            environment=resolved_environment,
            traffic=traffic,
            rollout=rollout,
            rollout_group=rollout_group,
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

            resolved_rollout = (
                rollout
                if rollout is not None
                else deployment.rollout_type
            )

            resolved_rollout_group = (
                rollout_group
                if rollout_group is not None
                else deployment.role
            )

            route = routing_repo.create_routing(
                routing_id=generate_random_id(
                    prefix="rtn"
                ),
                deployment_id=deployment_id,
                environment=resolved_environment,
                rollout_type=resolved_rollout,
                rollout_group=resolved_rollout_group,
                traffic_ratio=traffic,
                enabled=enabled,
                rules=route_rules,
                description=description,
                created_by=operator,
            )

            result = {
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
                    default=str,
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
            f"[cyan]{'TRAFFIC':<16}[/cyan] : "
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
                user=operator,
                source="cli",
                verbose=verbose,
                enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())
