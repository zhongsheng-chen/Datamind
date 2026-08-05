# datamind/cli/experiment/variant/add.py

"""添加实验分组命令

提供 A/B 实验分组添加功能。

核心功能：
  - add_variant: 添加实验分组

使用示例：
  python -m datamind.cli.main experiment variant add exp_0123456789abcdef \
    --name control \
    --deployment-id dep_control \
    --weight 0.5 \
    --control
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
from datamind.db.repositories import (
    DeploymentRepository,
    ExperimentRepository,
    VariantRepository,
)
from datamind.models.enums import ExperimentStatus, ExperimentVariantStatus
from datamind.models.errors import (
    ExperimentError,
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
)
from datamind.utils.datetime import format_iso_utc
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="添加实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("add")
def add_variant(
        experiment_id: str = typer.Argument(
            ...,
            help="实验 ID"
        ),
        name: str = typer.Option(
            ...,
            "--name",
            help="实验分组名称，例如 control / treatment"
        ),
        deployment_id: str = typer.Option(
            ...,
            "--deployment-id",
            help="部署 ID"
        ),
        weight: float = typer.Option(
            ...,
            "--weight",
            help="实验分组权重，范围 (0, 1]"
        ),
        control: bool = typer.Option(
            False,
            "--control",
            help="是否为对照组"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="分组描述"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """添加实验分组"""

    @audit(
        action="experiment.variant.add",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if not name:
            raise typer.BadParameter("--name 不能为空")

        if not deployment_id:
            raise typer.BadParameter("--deployment-id 不能为空")

        if weight <= 0 or weight > 1:
            raise typer.BadParameter("--weight 必须大于 0 且小于等于 1")

        logger.info(
            "开始添加实验分组",
            experiment_id=experiment_id,
            name=name,
            deployment_id=deployment_id,
            weight=weight,
            control=control,
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            experiment = await experiment_repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            deployment = await deployment_repo.get_deployment(deployment_id)

            if deployment is None:
                console.print(f"[red]部署不存在: {deployment_id}[/red]")
                raise typer.Exit(1)

            try:
                _validate_experiment_can_add_variant(
                    experiment
                )

                if deployment.model_id != experiment.model_id:
                    raise InvalidExperimentConfigError(
                        "部署所属模型与实验模型不一致\n"
                        f"实验模型 ID: {experiment.model_id}\n"
                        f"部署模型 ID: {deployment.model_id}"
                    )

                if deployment.environment != experiment.environment:
                    raise InvalidExperimentConfigError(
                        "部署环境与实验环境不一致\n"
                        f"实验环境: {experiment.environment}\n"
                        f"部署环境: {deployment.environment}"
                    )

                variants = await variant_repo.list_variants(
                    experiment_id=experiment_id,
                )

                if _has_active_variant_name(
                        variants=variants,
                        name=name,
                ):
                    raise InvalidExperimentConfigError(
                        f"实验已存在启用状态的同名分组: {name}"
                    )

                deployment_variant = _find_variant_by_deployment(
                        variants=variants,
                        deployment_id=deployment_id,
                )

                if deployment_variant is not None:
                    raise InvalidExperimentConfigError(
                        "实验已存在绑定该部署的分组: "
                        f"{deployment_variant.variant_id}"
                    )

                if control and _has_active_control_variant(variants):
                    raise InvalidExperimentConfigError(
                        "实验已存在启用状态的对照组，不能重复添加对照组"
                    )

            except ExperimentError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc

            config = _build_variant_config(
                name=name,
                deployment_id=deployment_id,
                environment=experiment.environment,
                weight=weight,
                is_control=control,
            )

            variant = variant_repo.create_variant(
                variant_id=generate_random_id(
                    prefix="var"
                ),
                experiment_id=experiment_id,
                name=name,
                deployment_id=deployment_id,
                weight=weight,
                is_control=control,
                status=ExperimentVariantStatus.ACTIVE,
                config=config,
                description=description,
                created_by=actor,
            )

            await variant_repo.flush()
            await uow.session.refresh(variant)

            result: dict[str, Any] = {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "model_id": experiment.model_id,
                "environment": experiment.environment,
                "name": variant.name,
                "deployment_id": variant.deployment_id,
                "weight": variant.weight,
                "is_control": variant.is_control,
                "status": variant.status,
                "config": variant.config,
                "description": variant.description,
                "created_by": variant.created_by,
                "created_at": format_iso_utc(variant.created_at),
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

        console.print("[green]实验分组创建成功[/green]\n")

        console.print(f"[cyan]{'VARIANT ID':<16}[/cyan] : {result['variant_id']}")
        console.print(f"[cyan]{'EXPERIMENT ID':<16}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name'] or '-'}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'WEIGHT':<16}[/cyan] : {result['weight']}")
        console.print(f"[cyan]{'CONTROL':<16}[/cyan] : {result['is_control']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())


def _validate_experiment_can_add_variant(
        experiment: Experiment,
) -> None:
    """校验实验是否允许添加分组"""
    status = str(experiment.status).lower()

    if status != str(ExperimentStatus.DRAFT):
        raise InvalidExperimentStateError(
            "只有 draft 状态的实验允许添加实验分组"
        )


def _build_variant_config(
        *,
        name: str,
        deployment_id: str,
        environment: str,
        weight: float,
        is_control: bool,
) -> dict:
    """构建实验分组配置"""
    return {
        "name": name,
        "deployment_id": deployment_id,
        "environment": environment,
        "weight": weight,
        "is_control": is_control,
        "group": "control" if is_control else "treatment",
    }


def _has_active_control_variant(
        variants: list[Variant],
) -> bool:
    """判断是否已存在启用状态的对照组"""
    return any(
        _is_active_variant(item) and _is_control_variant(item)
        for item in variants
    )


def _has_active_variant_name(
        *,
        variants: list[Variant],
        name: str,
) -> bool:
    """判断是否已存在启用状态的同名分组"""
    target_name = name.strip().lower()

    return any(
        _is_active_variant(item)
        and str(item.name or "").strip().lower() == target_name
        for item in variants
    )


def _find_variant_by_deployment(
        *,
        variants: list[Variant],
        deployment_id: str,
) -> Variant | None:
    """查找绑定指定部署的分组"""
    return next(
        (
            item
            for item in variants
            if item.deployment_id == deployment_id
        ),
        None,
    )


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
