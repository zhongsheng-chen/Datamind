# datamind/cli/experiment/variant/update.py

"""更新实验分组命令

提供 A/B 实验分组更新功能。

核心功能：
  - update_variant: 更新实验分组

使用示例：
  python -m datamind.cli.main experiment variant update var_0123456789abcdef \
    --name treatment_v2 \
    --weight 0.4

说明：
  - 实验处于 draft 状态，且实验分组处于 active 或 inactive 状态时，
    允许修改 name、deployment_id、weight、control、treatment 和 description。
  - 实验处于 paused 状态，且实验分组处于 active 或 inactive 状态时，
    仅允许修改 description。
  - 实验处于 running、stopped、completed 或 archived 状态时，不允许修改实验分组。
  - 实验分组处于 archived 状态时，不允许修改。
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
from datamind.db.models.variants import Variant
from datamind.db.repositories import (
    DeploymentRepository,
    ExperimentRepository,
    VariantRepository,
)
from datamind.models.enums import ExperimentVariantStatus
from datamind.models.errors import (
    ExperimentError,
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
)
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="更新实验分组命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)

EXPERIMENT_STATUS_DRAFT = "draft"
EXPERIMENT_STATUS_PAUSED = "paused"

VARIANT_STATUS_ACTIVE = str(ExperimentVariantStatus.ACTIVE)
VARIANT_STATUS_INACTIVE = str(ExperimentVariantStatus.INACTIVE)
VARIANT_STATUS_ARCHIVED = str(ExperimentVariantStatus.ARCHIVED)

DRAFT_UPDATE_FIELDS = {
    "name",
    "deployment_id",
    "weight",
    "is_control",
    "description",
}

PAUSED_UPDATE_FIELDS = {
    "description",
}


@app.command("update")
def update_variant(
        variant_id: str = typer.Argument(
            ...,
            help="实验分组 ID"
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            help="实验分组名称，例如 control / treatment"
        ),
        deployment_id: str | None = typer.Option(
            None,
            "--deployment-id",
            help="部署 ID"
        ),
        weight: float | None = typer.Option(
            None,
            "--weight",
            help="实验分组权重，范围 (0, 1]"
        ),
        control: bool = typer.Option(
            False,
            "--control",
            help="设置为对照组"
        ),
        treatment: bool = typer.Option(
            False,
            "--treatment",
            help="设置为实验组"
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
    """更新实验分组"""

    @audit(
        action="experiment.variant.update",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if control and treatment:
            raise typer.BadParameter("--control 与 --treatment 不能同时指定")

        requested_fields = _get_requested_fields(
            name=name,
            deployment_id=deployment_id,
            weight=weight,
            control=control,
            treatment=treatment,
            description=description,
        )

        if not requested_fields:
            raise typer.BadParameter("至少需要提供一个更新参数")

        if name is not None and not name:
            raise typer.BadParameter("--name 不能为空")

        if deployment_id is not None and not deployment_id:
            raise typer.BadParameter("--deployment-id 不能为空")

        if weight is not None and (
                weight <= 0 or weight > 1
        ):
            raise typer.BadParameter("--weight 必须大于 0 且小于等于 1")

        logger.info(
            "开始更新实验分组",
            variant_id=variant_id,
            requested_fields=sorted(requested_fields),
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            variant = await variant_repo.get_variant(variant_id)

            if variant is None:
                console.error(
                    f"分组更新失败：分组不存在：{variant_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            experiment = await experiment_repo.get_experiment(
                variant.experiment_id
            )

            if experiment is None:
                console.error(
                    "分组更新失败：关联实验不存在："
                    f"{variant.experiment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            experiment_status = _status_value(experiment.status)
            variant_status = _status_value(variant.status)

            target_deployment_id = (
                deployment_id
                if deployment_id is not None
                else variant.deployment_id
            )

            target_name = (
                name
                if name is not None
                else variant.name
            )

            target_is_control = _get_target_is_control(
                variant=variant,
                control=control,
                treatment=treatment,
            )

            target_variant_status = _status_value(variant.status)

            try:
                _validate_update_allowed(
                    experiment_status=experiment_status,
                    variant_status=variant_status,
                    requested_fields=requested_fields,
                )

                if deployment_id is not None:
                    deployment = await deployment_repo.get_deployment(
                        deployment_id
                    )

                    if deployment is None:
                        console.error(
                            f"分组更新失败：部署不存在：{deployment_id}",
                            output_format=output,
                        )
                        raise typer.Exit(code=1) from None

                    if deployment.model_id != experiment.model_id:
                        raise InvalidExperimentConfigError(
                            "部署模型与实验模型不一致\n"
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
                    experiment_id=variant.experiment_id,
                )

                if (
                        target_variant_status == VARIANT_STATUS_ACTIVE
                        and _has_other_active_variant_name(
                            variants=variants,
                            current_variant_id=variant.variant_id,
                            name=target_name,
                        )
                ):
                    raise InvalidExperimentConfigError(
                        f"实验已存在其他启用状态的同名分组: {target_name}"
                    )

                deployment_variant = _find_other_variant_by_deployment(
                        variants=variants,
                        current_variant_id=variant.variant_id,
                        deployment_id=target_deployment_id,
                )

                if deployment_variant is not None:
                    raise InvalidExperimentConfigError(
                        "实验已存在绑定该部署的其他分组: "
                        f"{deployment_variant.variant_id}"
                    )

                if (
                        target_is_control
                        and target_variant_status == VARIANT_STATUS_ACTIVE
                        and _has_other_active_control_variant(
                            variants=variants,
                            current_variant_id=variant.variant_id,
                        )
                ):
                    raise InvalidExperimentConfigError(
                        "实验已存在其他启用状态的对照组，不能将该分组设置为对照组"
                    )

            except ExperimentError as exc:
                console.error(
                    f"分组更新失败：{exc}",
                    output_format=output,
                    error_type=type(exc).__name__,
                )
                raise typer.Exit(code=1) from None

            if name is not None:
                variant.name = name

            if deployment_id is not None:
                variant.deployment_id = target_deployment_id

            if weight is not None:
                variant.weight = weight

            if control or treatment:
                variant.is_control = target_is_control

            if description is not None:
                variant.description = description

            variant.config = _build_variant_config(
                existing_config=variant.config,
                name=variant.name,
                deployment_id=variant.deployment_id,
                environment=experiment.environment,
                weight=variant.weight,
                is_control=variant.is_control,
            )
            variant.updated_by = actor

            await uow.session.flush()
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
                "updated_by": variant.updated_by,
                "updated_at": format_iso_utc(variant.updated_at),
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

        console.info("分组更新成功\n")

        console.print(f"{'VARIANT ID':<16} : {result['variant_id']}")
        console.print(f"{'EXPERIMENT ID':<16} : {result['experiment_id']}")
        console.print(f"{'MODEL ID':<16} : {result['model_id']}")
        console.print(f"{'ENVIRONMENT':<16} : {result['environment']}")
        console.print(f"{'NAME':<16} : {result['name'] or '-'}")
        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'WEIGHT':<16} : {result['weight']}")
        console.print(f"{'CONTROL':<16} : {result['is_control']}")
        console.print(f"{'STATUS':<16} : {result['status']}")
        console.print(
            f"{'DESCRIPTION':<16} : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"{'UPDATED BY':<16} : "
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
        name: str | None,
        deployment_id: str | None,
        weight: float | None,
        control: bool,
        treatment: bool,
        description: str | None,
) -> set[str]:
    """获取本次请求更新的字段"""
    fields = set()

    if name is not None:
        fields.add("name")

    if deployment_id is not None:
        fields.add("deployment_id")

    if weight is not None:
        fields.add("weight")

    if control or treatment:
        fields.add("is_control")

    if description is not None:
        fields.add("description")

    return fields


def _validate_update_allowed(
        *,
        experiment_status: str,
        variant_status: str,
        requested_fields: set[str],
) -> None:
    """校验实验状态和分组状态是否允许更新"""
    if variant_status == VARIANT_STATUS_ARCHIVED:
        raise InvalidExperimentStateError("归档状态下不允许修改分组")

    if variant_status not in {
        VARIANT_STATUS_ACTIVE,
        VARIANT_STATUS_INACTIVE,
    }:
        raise InvalidExperimentStateError(
            f"分组处于 {_variant_status_label(variant_status)}，不允许修改"
        )

    if experiment_status == EXPERIMENT_STATUS_DRAFT:
        disallowed = requested_fields - DRAFT_UPDATE_FIELDS

        if disallowed:
            raise InvalidExperimentStateError(
                "草稿状态下不允许修改字段："
                f"{', '.join(sorted(disallowed))}"
            )

        return

    if experiment_status == EXPERIMENT_STATUS_PAUSED:
        disallowed = requested_fields - PAUSED_UPDATE_FIELDS

        if disallowed:
            raise InvalidExperimentStateError(
                "暂停状态下仅允许修改分组描述"
            )

        return

    raise InvalidExperimentStateError(
        f"实验处于 {_experiment_status_label(experiment_status)}，"
        "不允许修改分组"
    )


def _experiment_status_label(
        status: str,
) -> str:
    """获取实验状态的终端显示名称"""
    labels = {
        "draft": "草稿状态",
        "running": "运行状态",
        "paused": "暂停状态",
        "stopped": "停止状态",
        "completed": "完成状态",
        "archived": "归档状态",
    }

    return labels.get(
        status,
        f"未知状态（{status}）",
    )


def _variant_status_label(
        status: str,
) -> str:
    """获取分组状态的终端显示名称"""
    labels = {
        "active": "启用状态",
        "inactive": "停用状态",
        "archived": "归档状态",
    }

    return labels.get(
        status,
        f"未知状态（{status}）",
    )


def _get_target_is_control(
        *,
        variant: Variant,
        control: bool,
        treatment: bool,
) -> bool:
    """获取更新后的对照组标记"""
    if control:
        return True

    if treatment:
        return False

    return bool(variant.is_control)


def _has_other_active_control_variant(
        *,
        variants: list[Variant],
        current_variant_id: str,
) -> bool:
    """判断是否存在其他启用状态的对照组"""
    return any(
        _status_value(item.status) == VARIANT_STATUS_ACTIVE
        and bool(item.is_control)
        and item.variant_id != current_variant_id
        for item in variants
    )


def _has_other_active_variant_name(
        *,
        variants: list[Variant],
        current_variant_id: str,
        name: str,
) -> bool:
    """判断是否存在其他启用状态的同名分组"""
    target_name = name.strip().lower()

    return any(
        _status_value(item.status) == VARIANT_STATUS_ACTIVE
        and item.variant_id != current_variant_id
        and str(item.name or "").strip().lower() == target_name
        for item in variants
    )


def _find_other_variant_by_deployment(
        *,
        variants: list[Variant],
        current_variant_id: str,
        deployment_id: str,
) -> Variant | None:
    """查找绑定指定部署的其他分组"""
    return next(
        (
            item
            for item in variants
            if (
                    item.variant_id != current_variant_id
                    and item.deployment_id == deployment_id
            )
        ),
        None,
    )


def _build_variant_config(
        *,
        existing_config,
        name: str,
        deployment_id: str,
        environment: str,
        weight: float,
        is_control: bool,
) -> dict:
    """构建实验分组配置"""
    config = (
        dict(existing_config)
        if isinstance(existing_config, dict)
        else {}
    )

    config.update({
        "name": name,
        "deployment_id": deployment_id,
        "environment": environment,
        "weight": weight,
        "is_control": is_control,
        "group": "control" if is_control else "treatment",
    })

    return config


def _status_value(
        status: Any,
) -> str:
    """获取状态字符串"""
    return str(status).lower()
