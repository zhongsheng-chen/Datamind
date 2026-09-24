"""更新路由命令.

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

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.config import get_settings
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    RoutingPatch,
    RoutingRepository,
)
from datamind.models.enums import DeploymentRole
from datamind.runtime.routing import RuleMatcher
from datamind.services.routing import validate_routing_allocation
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="更新路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)

CHAMPION_TRAFFIC_WARN_THRESHOLD = 0.7


@app.command("update")
def update_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID"
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            help="路由名称",
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
        effective_from: str | None = typer.Option(
            None,
            "--effective-from",
            help="生效时间"
        ),
        effective_to: str | None = typer.Option(
            None,
            "--effective-to",
            help="失效时间"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """更新路由规则.

    时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
    时区偏移。未提供时区偏移时，按配置时区解析。
    """
    settings = get_settings()
    timezone_name = settings.logging.timezone
    service_environment = settings.service.environment.value

    @audit(
        action="route.update",
        target_type="routing",
        target_id_func=lambda p, r: r["routing_id"],
    )
    async def _run(
            actor: str,
    ):
        resolved_name = None
        if name is not None:
            resolved_name = name.strip()
            if not resolved_name:
                raise typer.BadParameter("--name 不能为空")
            if len(resolved_name) > 128:
                raise typer.BadParameter("--name 不能超过 128 个字符")
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if traffic_ratio is not None and (
                traffic_ratio < 0 or traffic_ratio > 1
        ):
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

        if (
                name is None
                and traffic_ratio is None
                and rules_file is None
                and effective_from is None
                and effective_to is None
                and description is None
        ):
            raise typer.BadParameter(
                "至少需要提供一个更新参数"
            )

        logger.info(
            "开始更新路由",
            routing_id=routing_id,
            name=resolved_name,
            environment=service_environment,
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
                console.error(
                    f"更新路由失败：路由不存在：{routing_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            deployment = await deployment_repo.get_deployment(
                route.deployment_id
            )

            if deployment is None:
                console.error(
                    "更新路由失败：关联部署不存在："
                    f"{route.deployment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            if deployment.environment != service_environment:
                console.error(
                    "更新路由失败：路由环境与部署环境不一致\n"
                    f"部署环境：{deployment.environment}\n"
                    f"路由环境：{route.environment}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                effective_from_value = (
                    parse_datetime(
                        effective_from,
                        timezone_name=timezone_name,
                    )
                    if effective_from is not None
                    else getattr(route, "effective_from", None)
                )
                effective_to_value = (
                    parse_datetime(
                        effective_to,
                        timezone_name=timezone_name,
                    )
                    if effective_to is not None
                    else getattr(route, "effective_to", None)
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
                raise typer.BadParameter(
                    "--effective-to 必须晚于 --effective-from"
                )

            target_traffic_ratio = (
                traffic_ratio
                if traffic_ratio is not None
                else route.traffic_ratio
            )

            if (
                    str(deployment.role).lower()
                    == DeploymentRole.CHAMPION.value
                    and target_traffic_ratio < CHAMPION_TRAFFIC_WARN_THRESHOLD
            ):
                if output == "text":
                    console.warning(
                        "警告：champion 路由流量比例低于建议值，"
                        "请确认是否符合预期"
                    )

                logger.warning(
                    "champion 路由流量比例低于建议值",
                    routing_id=route.routing_id,
                    deployment_id=deployment.deployment_id,
                    role=deployment.role,
                    traffic_ratio=target_traffic_ratio,
                    warning_threshold=CHAMPION_TRAFFIC_WARN_THRESHOLD,
                )

            try:
                if route.enabled and traffic_ratio is not None:
                    await validate_routing_allocation(
                        routing_repo=routing_repo,
                        deployment_repo=deployment_repo,
                        deployment=deployment,
                        traffic_ratio=traffic_ratio,
                        exclude_routing_id=route.routing_id,
                    )

                patch = RoutingPatch(
                    name=resolved_name,
                    environment=Environment(service_environment),
                    rollout_type=deployment.rollout_type,
                    rollout_group=deployment.role,
                    traffic_ratio=traffic_ratio,
                    rules=route_rules,
                    effective_from=(
                        effective_from_value
                        if effective_from is not None
                        else None
                    ),
                    effective_to=(
                        effective_to_value
                        if effective_to is not None
                        else None
                    ),
                    description=description,
                )
                routing_repo.update_routing(
                    route,
                    patch,
                    updated_by=actor,
                )

            except ValueError as error:
                console.error(
                    f"更新路由失败：{error}",
                    output_format=output,
                    error_type=type(error).__name__,
                )
                raise typer.Exit(code=1) from None

            await uow.session.flush()
            await uow.session.refresh(route)

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

        console.info("路由更新成功\n")

        console.print(f"{'ROUTE NAME':<16} : {result['name']}")

        console.print(f"{'ROUTING ID':<16} : {result['routing_id']}")
        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'ROLLOUT TYPE':<16} : {result['rollout_type']}")
        console.print(
            f"{'ROLLOUT GROUP':<16} : "
            f"{result['rollout_group'] or '-'}"
        )
        console.print(f"{'TRAFFIC RATIO':<16} : {result['traffic_ratio']}")
        console.print(f"{'ENABLED':<16} : {result['enabled']}")

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
        console.print(
            f"{'UPDATED BY':<16} : "
            f"{result['updated_by'] or '-'}"
        )
        console.print(
            f"{'UPDATED AT':<16} : "
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
