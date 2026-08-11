# datamind/cli/experiment/variant/archive.py

"""归档实验分组命令

提供实验分组归档功能。

核心功能：
  - archive_variant: 归档实验分组

使用示例：
  python -m datamind.cli.main experiment variant archive var_0123456789abcdef
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
from datamind.db.repositories import VariantRepository
from datamind.models.errors import ExperimentError
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="归档实验分组命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("archive")
def archive_variant(
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
    """归档实验分组"""

    @audit(
        action="experiment.variant.archive",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始归档实验分组",
            variant_id=variant_id,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variant = await repo.get_variant(variant_id)

            if variant is None:
                console.error(
                    f"分组归档失败：分组不存在：{variant_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                repo.archive_variant(
                    variant,
                    updated_by=actor,
                )

            except ExperimentError as exc:
                console.error(
                    f"分组归档失败：{exc}",
                    output_format=output,
                    error_type=type(exc).__name__,
                )
                raise typer.Exit(code=1) from None

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

        console.info("分组归档成功\n")

        console.print(f"{'VARIANT ID':<16} : {result['variant_id']}")
        console.print(f"{'EXPERIMENT ID':<16} : {result['experiment_id']}")
        console.print(f"{'NAME':<16} : {result['name'] or '-'}")
        console.print(f"{'STATUS':<16} : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
