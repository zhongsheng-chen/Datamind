# datamind/cli/experiment/variant/activate.py

"""启用实验分组命令

提供实验分组启用功能。

核心功能：
  - activate_variant: 启用实验分组

使用示例：
  python -m datamind.cli.main experiment variant activate var_0123456789abcdef
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
from datamind.db.models.variants import Variant
from datamind.db.repositories import VariantRepository
from datamind.models.enums import ExperimentVariantStatus
from datamind.models.errors import (
    ExperimentError,
    InvalidExperimentConfigError,
)
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="启用实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("activate")
def activate_variant(
        variant_id: str = typer.Argument(
            ...,
            help="实验分组 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """启用实验分组"""

    @audit(
        action="experiment.variant.activate",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始启用实验分组",
            variant_id=variant_id,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variant = await repo.get_variant(variant_id)

            if variant is None:
                console.print(f"[red]实验分组不存在: {variant_id}[/red]")
                raise typer.Exit(1)

            try:
                variants = await repo.list_variants(
                    experiment_id=variant.experiment_id,
                    deployment_id=variant.deployment_id,
                    status=ExperimentVariantStatus.ACTIVE,
                )

                if _has_other_active_variant(
                        variants=variants,
                        current_variant_id=variant.variant_id,
                ):
                    raise InvalidExperimentConfigError(
                        "实验已存在绑定该部署的其他启用状态分组: "
                        f"{variant.deployment_id}"
                    )

                repo.activate_variant(
                    variant,
                    updated_by=actor,
                )

            except ExperimentError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc

            await uow.session.flush()
            await uow.session.refresh(variant)

            result: dict[str, Any] = {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "name": variant.name,
                "deployment_id": variant.deployment_id,
                "weight": variant.weight,
                "is_control": variant.is_control,
                "status": variant.status,
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

        console.print("[green]实验分组启用成功[/green]\n")

        console.print(f"[cyan]{'VARIANT ID':<16}[/cyan] : {result['variant_id']}")
        console.print(f"[cyan]{'EXPERIMENT ID':<16}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name'] or '-'}")
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


def _has_other_active_variant(
        *,
        variants: list[Variant],
        current_variant_id: str,
) -> bool:
    """判断查询结果中是否包含其他启用状态分组"""
    return any(
        item.variant_id != current_variant_id
        for item in variants
    )
