# datamind/cli/experiment/variant/deactivate.py

"""停用实验分组命令

提供实验分组停用功能。

核心功能：
  - deactivate_variant: 停用实验分组

使用示例：
  python -m datamind.cli.main experiment variant deactivate var_a1b2c3d4 --operator admin
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import VariantRepository
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="停用实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("deactivate")
def deactivate_variant(
    variant_id: str = typer.Argument(
        ...,
        help="实验分组 ID"
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
        help="显示调试日志"
    ),
):
    """停用实验分组"""

    @audit(
        action="experiment.variant.deactivate",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始停用实验分组",
            variant_id=variant_id,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variant = await repo.get_variant(variant_id)

            if variant is None:
                console.print(f"[red]实验分组不存在: {variant_id}[/red]")
                raise typer.Exit(1)

            repo.deactivate_variant(
                variant,
                updated_by=operator,
            )

            await repo.flush()

            result = {
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
                    default=str,
                )
            )
            return result

        console.print("[green]实验分组停用成功[/green]\n")

        console.print(f"[cyan]{'VARIANT ID':<16}[/cyan] : {result['variant_id']}")
        console.print(f"[cyan]{'EXPERIMENT ID':<16}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

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