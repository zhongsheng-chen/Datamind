# datamind/cli/experiment/start.py

"""启动实验命令

提供实验启动功能。

核心功能：
  - start_experiment: 启动实验

使用示例：
  python -m datamind.cli.main experiment start exp_0123456789abcdef
"""

import asyncio
import json
from datetime import (
    datetime,
    timezone,
)
from typing import Any

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.models.deployments import Deployment
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.db.repositories import (
    DeploymentRepository,
    ExperimentRepository,
    VariantRepository,
)
from datamind.models.enums import (
    AssignmentStrategy,
    DeploymentStatus,
    ExperimentVariantStatus,
)
from datamind.models.errors import ExperimentError, InvalidExperimentConfigError
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
    to_utc,
)

app = typer.Typer(help="启动实验命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)

TREATMENT_TRAFFIC_RATIO_WARN_THRESHOLD = 0.5


@app.command("start")
def start_experiment(
        experiment_id: str = typer.Argument(
            ...,
            help="实验 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """启动实验"""

    @audit(
        action="experiment.start",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始启动实验",
            experiment_id=experiment_id,
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            experiment = await experiment_repo.get_experiment(experiment_id)

            if experiment is None:
                console.error(
                    f"实验启动失败：实验不存在：{experiment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                running_experiment = await experiment_repo.get_running_experiment(
                    model_id=experiment.model_id,
                    environment=Environment(
                        experiment.environment
                    ),
                    exclude_experiment_id=experiment.experiment_id,
                )

                if running_experiment is not None:
                    raise InvalidExperimentConfigError(
                        "模型在当前环境下已存在运行中的实验，请先暂停、停止或完成已有实验后再启动新实验\n"
                        f"模型 ID: {experiment.model_id}\n"
                        f"实验环境: {experiment.environment}\n"
                        f"运行中实验 ID: {running_experiment.experiment_id}"
                    )

                strategy = _get_experiment_strategy(experiment)

                variants = await variant_repo.list_variants(
                    experiment_id=experiment_id,
                )

                active_variants = [
                    item
                    for item in variants
                    if _is_active_variant(item)
                ]

                if not active_variants:
                    raise InvalidExperimentConfigError(
                        "实验没有可用的启用状态分组，请先添加实验分组"
                    )

                await _validate_active_variant_deployments(
                    deployment_repo=deployment_repo,
                    experiment=experiment,
                    active_variants=active_variants,
                    now=datetime.now(
                        timezone.utc
                    ),
                )

                control_count = sum(
                    1
                    for item in active_variants
                    if _is_control_variant(item)
                )

                if control_count != 1:
                    raise InvalidExperimentConfigError(
                        "实验必须且只能包含一个启用状态的对照组"
                    )

                treatment_count = sum(
                    1
                    for item in active_variants
                    if not _is_control_variant(item)
                )

                if treatment_count < 1:
                    raise InvalidExperimentConfigError(
                        "实验至少需要包含一个启用状态的实验组"
                    )

                total_weight = sum(
                    _variant_weight(item)
                    for item in active_variants
                )

                treatment_traffic_ratio = None
                warnings = []

                if strategy == AssignmentStrategy.HASH:
                    if abs(total_weight - 1.0) > 0.000001:
                        raise InvalidExperimentConfigError(
                            "hash 策略下启用状态分组的权重之和必须等于 1"
                        )

                    treatment_traffic_ratio = sum(
                        _variant_weight(item)
                        for item in active_variants
                        if not _is_control_variant(item)
                    )

                    if (
                            treatment_traffic_ratio
                            > TREATMENT_TRAFFIC_RATIO_WARN_THRESHOLD
                    ):
                        warning_message = (
                            "实验组总流量比例超过 50%，"
                            "请确认实验流量分配是否符合预期"
                        )

                        warnings.append(warning_message)

                        if output == "text":
                            console.warning(
                                f"警告：{warning_message}"
                            )

                        logger.warning(
                            "实验组总流量比例超过建议值",
                            experiment_id=experiment_id,
                            treatment_traffic_ratio=treatment_traffic_ratio,
                            warning_threshold=TREATMENT_TRAFFIC_RATIO_WARN_THRESHOLD,
                        )

                else:
                    logger.info(
                        "manual 策略跳过权重总和校验和实验组流量比例告警",
                        experiment_id=experiment_id,
                        strategy=strategy,
                        active_variant_count=len(active_variants),
                        total_weight=total_weight,
                    )

                experiment_repo.start_experiment(
                    experiment,
                    updated_by=actor,
                )

            except ExperimentError as exc:
                console.error(
                    f"实验启动失败：{exc}",
                    output_format=output,
                    error_type=type(exc).__name__,
                )
                raise typer.Exit(code=1) from None

            await uow.session.flush()
            await uow.session.refresh(experiment)

            result: dict[str, Any] = {
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "environment": experiment.environment,
                "name": experiment.name,
                "status": experiment.status,
                "strategy": strategy,
                "effective_from": (
                    format_iso_utc(experiment.effective_from)
                    if experiment.effective_from is not None
                    else None
                ),
                "effective_to": (
                    format_iso_utc(experiment.effective_to)
                    if experiment.effective_to is not None
                    else None
                ),
                "active_variant_count": len(active_variants),
                "control_variant_count": control_count,
                "treatment_variant_count": treatment_count,
                "active_weight_sum": total_weight,
                "treatment_traffic_ratio": treatment_traffic_ratio,
                "warnings": warnings,
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

        console.info("实验启动成功\n")
        console.print(f"{'EXPERIMENT ID':<18} : {result['experiment_id']}")
        console.print(f"{'MODEL ID':<18} : {result['model_id']}")
        console.print(f"{'ENVIRONMENT':<18} : {result['environment']}")
        console.print(f"{'STATUS':<18} : {result['status']}")
        console.print(f"{'STRATEGY':<18} : {result['strategy']}")
        console.print(
            f"{'EFFECTIVE FROM':<18} : "
            f"{format_datetime(parse_datetime(result['effective_from']))}"
        )
        effective_to_text = (
            format_datetime(
                parse_datetime(
                    result["effective_to"]
                )
            )
            if result["effective_to"]
            else "-"
        )
        console.print(
            f"{'EFFECTIVE TO':<18} : "
            f"{effective_to_text}"
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


async def _validate_active_variant_deployments(
        *,
        deployment_repo: DeploymentRepository,
        experiment: Experiment,
        active_variants: list[Variant],
        now: datetime,
) -> None:
    """校验启用状态实验分组绑定的部署"""
    deployment_variants: dict[str, str] = {}

    for variant in active_variants:
        existing_variant_id = deployment_variants.get(
            variant.deployment_id
        )

        if existing_variant_id is not None:
            raise InvalidExperimentConfigError(
                "启用状态实验分组必须绑定不同部署\n"
                f"部署 ID: {variant.deployment_id}\n"
                "实验分组 ID: "
                f"{existing_variant_id}, {variant.variant_id}"
            )

        deployment_variants[
            variant.deployment_id
        ] = variant.variant_id

    for variant in active_variants:
        deployment = await deployment_repo.get_deployment(
            variant.deployment_id
        )

        if deployment is None:
            raise InvalidExperimentConfigError(
                "实验分组绑定的部署不存在\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"部署 ID: {variant.deployment_id}"
            )

        if deployment.model_id != experiment.model_id:
            raise InvalidExperimentConfigError(
                "实验分组绑定的部署所属模型与实验模型不一致\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"实验模型 ID: {experiment.model_id}\n"
                f"部署模型 ID: {deployment.model_id}"
            )

        if deployment.environment != experiment.environment:
            raise InvalidExperimentConfigError(
                "实验分组绑定的部署环境与实验环境不一致\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"实验环境: {experiment.environment}\n"
                f"部署环境: {deployment.environment}"
            )

        if (
                str(deployment.rollout_type).lower()
                == "shadow"
                or str(deployment.role).lower()
                == "shadow"
        ):
            raise InvalidExperimentConfigError(
                "实验分组不能使用影子部署\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"部署 ID: {deployment.deployment_id}"
            )

        if deployment.status != str(
                DeploymentStatus.ACTIVE
        ):
            raise InvalidExperimentConfigError(
                "实验分组绑定的部署未启用\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"部署 ID: {deployment.deployment_id}\n"
                f"部署状态: {deployment.status}"
            )

        if not _is_effective_deployment(
                deployment,
                now=now,
        ):
            raise InvalidExperimentConfigError(
                "实验分组绑定的部署不在生效时间内\n"
                f"实验分组 ID: {variant.variant_id}\n"
                f"部署 ID: {deployment.deployment_id}"
            )


def _is_effective_deployment(
        deployment: Deployment,
        *,
        now: datetime,
) -> bool:
    """判断部署是否处于生效时间窗口"""
    current_time = to_utc(
        now
    )
    effective_from = deployment.effective_from

    if effective_from is not None:
        start_time = to_utc(
            effective_from
        )

        if start_time > current_time:
            return False

    effective_to = deployment.effective_to

    if effective_to is not None:
        end_time = to_utc(
            effective_to
        )

        if end_time <= current_time:
            return False

    return True


def _get_experiment_strategy(
        experiment: Experiment,
) -> AssignmentStrategy:
    """获取实验分配策略"""
    config = _get_config(experiment)

    value = config.get(
        "strategy",
        AssignmentStrategy.HASH,
    )

    value = str(
        value or AssignmentStrategy.HASH
    ).lower()

    try:
        return AssignmentStrategy(value)

    except ValueError as exc:
        raise InvalidExperimentConfigError(
            f"不支持的实验分配策略: {value}"
        ) from exc


def _get_config(
        experiment: Experiment,
) -> dict:
    """获取实验配置"""
    config = experiment.config or {}

    if not isinstance(config, dict):
        raise InvalidExperimentConfigError(
            "实验配置 config 必须是 JSON 对象"
        )

    return config


def _is_active_variant(
        variant: Variant,
) -> bool:
    """判断实验分组是否为启用状态"""
    return (
        str(variant.status).lower()
        == str(ExperimentVariantStatus.ACTIVE)
    )


def _is_control_variant(
        variant: Variant,
) -> bool:
    """判断实验分组是否为对照组"""
    return bool(variant.is_control)


def _variant_weight(
        variant: Variant,
) -> float:
    """获取实验分组权重"""
    return float(variant.weight or 0)
