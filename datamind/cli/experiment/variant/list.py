# datamind/cli/experiment/variant/list.py

"""列出实验分组命令

提供实验分组列表查询功能。

核心功能：
  - list_variants: 列出实验分组

使用示例：
  python -m datamind.cli.main experiment variant list exp_a1b2c3d4
"""

import asyncio
import json

import typer
import structlog
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import VariantRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="列出实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_variants(
    experiment_id: str = typer.Argument(
        ...,
        help="实验 ID"
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="实验分组状态：active/inactive/archived"
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
    """列出实验分组"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始列出实验分组",
            experiment_id=experiment_id,
            status=status,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variants = await repo.list_variants(
                experiment_id=experiment_id,
                status=status,
            )

        if output == "json":
            result = []

            for item in variants:
                result.append({
                    "variant_id": item.variant_id,
                    "experiment_id": item.experiment_id,
                    "name": item.name,
                    "deployment_id": item.deployment_id,
                    "weight": item.weight,
                    "is_control": item.is_control,
                    "status": item.status,
                    "config": item.config,
                    "description": item.description,
                    "created_by": item.created_by,
                    "created_at": format_iso_utc(item.created_at),
                    "updated_by": item.updated_by,
                    "updated_at": format_iso_utc(item.updated_at),
                })

            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return result

        console.print(f"[dim]共找到 {len(variants)} 个实验分组[/dim]\n")

        if not variants:
            return variants

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("VARIANT ID")
        table.add_column("NAME")
        table.add_column("DEPLOYMENT ID")
        table.add_column("WEIGHT")
        table.add_column("CONTROL")
        table.add_column("STATUS")
        table.add_column("UPDATED AT")

        for item in variants:
            table.add_row(
                item.variant_id,
                item.name,
                item.deployment_id,
                str(item.weight),
                str(item.is_control),
                item.status,
                format_datetime(item.updated_at),
            )

        console.print(table)

        return variants

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())