# datamind/cli/experiment/update.py

"""更新实验命令

提供 A/B 实验配置更新功能。

核心功能：
  - update_experiment: 更新实验

使用示例：
  python -m datamind.cli.main experiment update exp_0123456789abcdef \
    --name scorecard_ab_test_v2 \
    --environment development \
    --traffic-ratio 0.3 \
    --bucket-key customer_id

说明：
  - 实验处于 draft 状态时，允许修改 environment、name、description、
    strategy、traffic_ratio、bucket_key、effective_from 和 effective_to。
  - 实验处于 paused 状态时，仅允许修改 description 和 effective_to。
  - 实验处于 running、stopped、completed 或 archived 状态时，不允许修改。
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
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.db.repositories import ExperimentRepository, VariantRepository
from datamind.models.enums import AssignmentStrategy
from datamind.models.errors import (
    ExperimentError,
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
)
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="更新实验命令")
console = Console()

logger = structlog.get_logger(__name__)

EXPERIMENT_STATUS_DRAFT = "draft"
EXPERIMENT_STATUS_PAUSED = "paused"

DRAFT_UPDATE_FIELDS = {
    "environment",
    "name",
    "description",
    "strategy",
    "traffic_ratio",
    "bucket_key",
    "effective_from",
    "effective_to",
}

PAUSED_UPDATE_FIELDS = {
    "description",
    "effective_to",
}


@app.command("update")
def update_experiment(
        experiment_id: str = typer.Argument(
            ...,
            help="实验 ID"
        ),
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="实验环境"
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            help="实验名称"
        ),
        strategy: str | None = typer.Option(
            None,
            "--strategy",
            help="实验分配策略，可选值：hash / manual"
        ),
        traffic_ratio: float | None = typer.Option(
            None,
            "--traffic-ratio",
            help="实验流量比例；hash 策略取值范围为 (0, 1]，manual 策略取值范围为 [0, 1]"
        ),
        bucket_key: str | None = typer.Option(
            None,
            "--bucket-key",
            help="分桶主体字段，例如 customer_id / order_id / apply_id"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="实验描述"
        ),
        effective_from: str | None = typer.Option(
            None,
            "--effective-from",
            help="生效开始时间，ISO 格式，例如 2026-07-01T09:00:00+08:00"
        ),
        effective_to: str | None = typer.Option(
            None,
            "--effective-to",
            help="生效结束时间，ISO 格式，例如 2026-07-31T23:59:59+08:00"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """更新实验"""

    @audit(
        action="experiment.update",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        requested_fields = _get_requested_fields(
            environment=environment,
            name=name,
            strategy=strategy,
            traffic_ratio=traffic_ratio,
            bucket_key=bucket_key,
            description=description,
            effective_from=effective_from,
            effective_to=effective_to,
        )

        if not requested_fields:
            raise typer.BadParameter("至少需要提供一个更新参数")

        if environment is not None and not environment:
            raise typer.BadParameter("--environment 不能为空")

        if name is not None and not name:
            raise typer.BadParameter("--name 不能为空")

        if bucket_key is not None and not bucket_key:
            raise typer.BadParameter("--bucket-key 不能为空")

        parsed_effective_from = _parse_optional_datetime(
            value=effective_from,
            option_name="--effective-from",
        )
        parsed_effective_to = _parse_optional_datetime(
            value=effective_to,
            option_name="--effective-to",
        )

        logger.info(
            "开始更新实验",
            experiment_id=experiment_id,
            requested_fields=sorted(requested_fields),
            environment=environment,
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            experiment = await experiment_repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            experiment_status = str(experiment.status).lower()

            try:
                _validate_update_allowed(
                    experiment_status=experiment_status,
                    requested_fields=requested_fields,
                )

                if (
                        environment is not None
                        and environment != experiment.environment
                ):
                    variants = await variant_repo.list_variants(
                        experiment_id=experiment_id,
                    )

                    _validate_experiment_can_update_environment(
                        variants=variants,
                    )

                config = _get_config(experiment)

                target_strategy = _get_target_strategy(
                    config=config,
                    strategy=strategy,
                )
                target_traffic_ratio = _get_target_traffic_ratio(
                    config=config,
                    traffic_ratio=traffic_ratio,
                )

                if traffic_ratio is not None or strategy is not None:
                    _validate_traffic_ratio(
                        strategy=target_strategy,
                        traffic_ratio=target_traffic_ratio,
                    )

            except ExperimentError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc

            target_effective_from = (
                parsed_effective_from
                if parsed_effective_from is not None
                else experiment.effective_from
            )
            target_effective_to = (
                parsed_effective_to
                if parsed_effective_to is not None
                else experiment.effective_to
            )

            if (
                    target_effective_from is not None
                    and target_effective_to is not None
                    and target_effective_to <= target_effective_from
            ):
                raise typer.BadParameter(
                    "--effective-to 必须晚于 --effective-from"
                )

            if environment is not None:
                experiment.environment = environment

            if name is not None:
                experiment.name = name

            if description is not None:
                experiment.description = description

            if parsed_effective_from is not None:
                experiment.effective_from = parsed_effective_from

            if parsed_effective_to is not None:
                experiment.effective_to = parsed_effective_to

            if strategy is not None:
                config["strategy"] = str(target_strategy)

            if traffic_ratio is not None:
                config["traffic_ratio"] = target_traffic_ratio

            if bucket_key is not None:
                config["bucket_key"] = bucket_key

            experiment.config = config
            experiment.updated_by = actor

            await uow.session.flush()
            await uow.session.refresh(experiment)

            result: dict[str, Any] = {
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "environment": experiment.environment,
                "name": experiment.name,
                "status": experiment.status,
                "config": experiment.config,
                "description": experiment.description,
                "effective_from": format_iso_utc(experiment.effective_from),
                "effective_to": format_iso_utc(experiment.effective_to),
                "updated_by": experiment.updated_by,
                "updated_at": format_iso_utc(experiment.updated_at),
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

        console.print("[green]实验更新成功[/green]\n")

        console.print(f"[cyan]{'EXPERIMENT ID':<18}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<18}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'NAME':<18}[/cyan] : {result['name'] or '-'}")
        console.print(f"[cyan]{'STATUS':<18}[/cyan] : {result['status']}")
        console.print(
            f"[cyan]{'STRATEGY':<18}[/cyan] : "
            f"{result['config'].get('strategy', '-')}"
        )
        console.print(
            f"[cyan]{'TRAFFIC RATIO':<18}[/cyan] : "
            f"{result['config'].get('traffic_ratio', '-')}"
        )
        console.print(
            f"[cyan]{'BUCKET KEY':<18}[/cyan] : "
            f"{result['config'].get('bucket_key', '-')}"
        )
        console.print(
            f"[cyan]{'DESCRIPTION':<18}[/cyan] : "
            f"{result['description'] or '-'}"
        )
        for label, field in (
                ("EFFECTIVE FROM", "effective_from"),
                ("EFFECTIVE TO", "effective_to"),
        ):
            value = (
                format_datetime(
                    parse_datetime(
                        result[field]
                    )
                )
                if result[field]
                else "-"
            )
            console.print(
                f"[cyan]{label:<18}[/cyan] : "
                f"{value}"
            )
        console.print(
            f"[cyan]{'UPDATED BY':<18}[/cyan] : "
            f"{result['updated_by'] or '-'}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())


def _get_requested_fields(
        *,
        environment: str | None,
        name: str | None,
        strategy: str | None,
        traffic_ratio: float | None,
        bucket_key: str | None,
        description: str | None,
        effective_from: str | None,
        effective_to: str | None,
) -> set[str]:
    """获取本次请求更新的字段"""
    fields = set()

    if environment is not None:
        fields.add("environment")

    if name is not None:
        fields.add("name")

    if strategy is not None:
        fields.add("strategy")

    if traffic_ratio is not None:
        fields.add("traffic_ratio")

    if bucket_key is not None:
        fields.add("bucket_key")

    if description is not None:
        fields.add("description")

    if effective_from is not None:
        fields.add("effective_from")

    if effective_to is not None:
        fields.add("effective_to")

    return fields


def _validate_update_allowed(
        *,
        experiment_status: str,
        requested_fields: set[str],
) -> None:
    """校验实验当前状态是否允许更新"""
    if experiment_status == EXPERIMENT_STATUS_DRAFT:
        disallowed = requested_fields - DRAFT_UPDATE_FIELDS

        if disallowed:
            raise InvalidExperimentStateError(
                "draft 状态不允许修改字段: "
                f"{', '.join(sorted(disallowed))}"
            )

        return

    if experiment_status == EXPERIMENT_STATUS_PAUSED:
        disallowed = requested_fields - PAUSED_UPDATE_FIELDS

        if disallowed:
            raise InvalidExperimentStateError(
                "paused 状态只允许修改 description 和 effective_to"
            )

        return

    raise InvalidExperimentStateError(
        f"{experiment_status} 状态不允许修改实验"
    )


def _validate_experiment_can_update_environment(
        *,
        variants: list[Variant],
) -> None:
    """校验实验是否允许修改环境"""
    if not variants:
        return

    raise InvalidExperimentConfigError(
        "实验已存在分组，不允许修改 environment；"
        "如需更换环境，请新建实验"
    )


def _get_target_strategy(
        *,
        config: dict,
        strategy: str | None,
) -> AssignmentStrategy:
    """获取更新后的实验分配策略"""
    value = (
        strategy
        if strategy is not None
        else config.get("strategy")
    )

    value = str(
        value or AssignmentStrategy.HASH
    ).lower()

    try:
        return AssignmentStrategy(value)

    except ValueError as exc:
        raise typer.BadParameter(
            "--strategy 只支持 hash 或 manual"
        ) from exc


def _get_target_traffic_ratio(
        *,
        config: dict,
        traffic_ratio: float | None,
) -> float:
    """获取更新后的实验流量比例"""
    if traffic_ratio is not None:
        return traffic_ratio

    value = config.get(
        "traffic_ratio",
        1.0,
    )

    try:
        return float(value)

    except (TypeError, ValueError) as exc:
        raise InvalidExperimentConfigError(
            "实验配置中的 traffic_ratio 不是有效数字"
        ) from exc


def _validate_traffic_ratio(
        *,
        strategy: AssignmentStrategy,
        traffic_ratio: float,
) -> None:
    """校验实验流量比例"""
    if traffic_ratio < 0 or traffic_ratio > 1:
        raise typer.BadParameter(
            "--traffic-ratio 必须在 0 到 1 之间"
        )

    if (
            strategy == AssignmentStrategy.HASH
            and traffic_ratio <= 0
    ):
        raise typer.BadParameter(
            "hash 策略下 --traffic-ratio 必须大于 0"
        )


def _get_config(
        experiment: Experiment,
) -> dict:
    """获取实验配置"""
    config = experiment.config or {}

    if not isinstance(config, dict):
        raise InvalidExperimentConfigError(
            "实验配置 config 必须是 JSON 对象"
        )

    return dict(config)


def _parse_optional_datetime(
        *,
        value: str | None,
        option_name: str,
):
    """解析可选日期时间参数"""
    if value is None:
        return None

    try:
        return parse_datetime(value)

    except ValueError as exc:
        raise typer.BadParameter(
            f"{option_name} 时间格式错误，请使用 ISO 格式"
        ) from exc
