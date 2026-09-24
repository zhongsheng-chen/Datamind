"""创建路由命令.

提供模型路由规则创建功能。

核心功能：
  - create_route: 创建路由规则

使用示例：
  python -m datamind.cli.main route create dep_0123456789abcdef \
    --name scorecard-route \
    --traffic-ratio 0.8 \
    --rules-file route_rules.json
"""

import asyncio
import json
from typing import Any

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingRepository,
)
from datamind.models.enums import DeploymentRole
from datamind.runtime.routing import RuleMatcher
from datamind.services.routing import (
    ensure_deployment_has_no_routing,
    validate_routing_allocation,
)
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="创建路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)

CHAMPION_TRAFFIC_RATIO_WARN_THRESHOLD = 0.7


@app.command("create")
def create_route(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        name: str = typer.Option(
            ...,
            "--name",
            help="路由名称",
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
        effective_from: str | None = typer.Option(
            None,
            "--effective-from",
            help="生效时间。默认不设置"
        ),
        effective_to: str | None = typer.Option(
            None,
            "--effective-to",
            help="失效时间。默认不设置"
        ),
        enabled: bool = typer.Option(
            False,
            "--enabled/--disabled",
            help="是否启用路由"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """创建路由规则.

    时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
    时区偏移。未提供时区偏移时，按配置时区解析。
    """
    settings = get_settings()
    service_config = settings.service
    timezone_name = settings.logging.timezone

    environment = service_config.environment

    @audit(
        action="route.create",
        target_type="routing",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run(
            actor: str,
    ):
        resolved_name = name.strip()
        if not resolved_name:
            raise typer.BadParameter("--name 不能为空")
        if len(resolved_name) > 128:
            raise typer.BadParameter("--name 不能超过 128 个字符")
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if traffic_ratio < 0 or traffic_ratio > 1:
            raise typer.BadParameter(
                "--traffic-ratio 必须在 0 到 1 之间"
            )

        try:
            effective_from_value = parse_datetime(
                effective_from,
                timezone_name=timezone_name,
            )
            effective_to_value = parse_datetime(
                effective_to,
                timezone_name=timezone_name,
            )

        except ValueError as datetime_error:
            raise typer.BadParameter(
                "生效时间格式无效，请使用 "
                "YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式"
            ) from datetime_error

        if (
                effective_from_value is not None
                and effective_to_value is not None
                and effective_to_value <= effective_from_value
        ):
            raise typer.BadParameter("--effective-to 必须晚于 --effective-from")

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

            except FileNotFoundError as error:
                raise typer.BadParameter(
                    f"--rules-file 文件不存在：{rules_file}"
                ) from error

            except json.JSONDecodeError as error:
                raise typer.BadParameter(
                    "--rules-file JSON 解析失败："
                    f"{error}"
                ) from error

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

            except ValueError as error:
                raise typer.BadParameter(
                    "--rules-file 规则校验失败："
                    f"{error}"
                ) from error

        logger.info(
            "开始创建路由",
            name=resolved_name,
            deployment_id=deployment_id,
            environment=environment,
            traffic_ratio=traffic_ratio,
            rules_file=rules_file,
            enabled=enabled,
            effective_from=effective_from_value,
            effective_to=effective_to_value,
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
                console.error(
                    f"创建路由失败：部署不存在：{deployment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            if deployment.environment != environment:
                console.error(
                    "创建路由失败：路由环境与部署环境不一致\n"
                    f"部署环境：{deployment.environment}\n"
                    f"路由环境：{environment}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                await ensure_deployment_has_no_routing(
                    routing_repo=routing_repo,
                    deployment_id=deployment_id,
                )
                if enabled:
                    await validate_routing_allocation(
                        routing_repo=routing_repo,
                        deployment_repo=deployment_repo,
                        deployment=deployment,
                        traffic_ratio=traffic_ratio,
                    )
            except ValueError as error:
                console.error(
                    f"创建路由失败：{error}",
                    output_format=output,
                    error_type=type(error).__name__,
                )
                raise typer.Exit(code=1) from None

            if (
                    str(deployment.role).lower()
                    == DeploymentRole.CHAMPION.value
                    and traffic_ratio < CHAMPION_TRAFFIC_RATIO_WARN_THRESHOLD
            ):
                if output == "text":
                    console.warning(
                        "警告：champion 路由流量比例低于 0.7，"
                        "请确认是否符合预期"
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
                name=resolved_name,
                deployment_id=deployment_id,
                environment=environment,
                rollout_type=deployment.rollout_type,
                rollout_group=deployment.role,
                traffic_ratio=traffic_ratio,
                enabled=enabled,
                rules=route_rules,
                effective_from=effective_from_value,
                effective_to=effective_to_value,
                description=description,
                created_by=actor,
            )

            result: dict[str, Any] = {
                "routing_id": route.routing_id,
                "name": route.name,
                "deployment_id": route.deployment_id,
                "environment": route.environment,
                "rollout_type": route.rollout_type,
                "rollout_group": route.rollout_group,
                "traffic_ratio": route.traffic_ratio,
                "enabled": route.enabled,
                "rules": route.rules,
                "effective_from": format_iso_utc(route.effective_from),
                "effective_to": format_iso_utc(route.effective_to),
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

        console.info("路由创建成功\n")

        console.print(
            f"{'ROUTE NAME':<16} : "
            f"{result['name']}"
        )

        console.print(
            f"{'ROUTING ID':<16} : "
            f"{result['routing_id']}"
        )
        console.print(
            f"{'DEPLOYMENT ID':<16} : "
            f"{result['deployment_id']}"
        )
        console.print(
            f"{'ROLLOUT TYPE':<16} : "
            f"{result['rollout_type']}"
        )
        console.print(
            f"{'ROLLOUT GROUP':<16} : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(
            f"{'TRAFFIC RATIO':<16} : "
            f"{result['traffic_ratio']}"
        )
        console.print(
            f"{'ENABLED':<16} : "
            f"{result['enabled']}"
        )

        if result["rules"]:
            console.print(
                f"{'RULES':<16} : "
                f"{json.dumps(result['rules'], ensure_ascii=False)}"
            )

        for label, field in (
                ("EFFECTIVE FROM", "effective_from"),
                ("EFFECTIVE TO", "effective_to"),
        ):
            value = format_datetime(
                parse_datetime(result[field]),
                timezone_name=timezone_name,
            )
            console.print(f"{label:<16} : {value}")

        console.print(
            f"{'DESCRIPTION':<16} : "
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
