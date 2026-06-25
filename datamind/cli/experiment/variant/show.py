# datamind/cli/experiment/variant/show.py

"""查看实验分组命令

提供实验分组详情查看功能。

核心功能：
  - show_variant: 查看实验分组详情

使用示例：
  python -m datamind.cli.main experiment variant show var_a1b2c3d4
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import VariantRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="查看实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_variant(
    variant_id: str = typer.Argument(
        ...,
        help="实验分组 ID"
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
    """查看实验分组详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看实验分组详情",
            variant_id=variant_id,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variant = await repo.get_variant(variant_id)

            if variant is None:
                console.print(f"[red]实验分组不存在: {variant_id}[/red]")
                raise typer.Exit(1)

        result = {
            "variant_id": variant.variant_id,
            "experiment_id": variant.experiment_id,
            "name": variant.name,
            "deployment_id": variant.deployment_id,
            "weight": variant.weight,
            "is_control": variant.is_control,
            "status": variant.status,
            "config": variant.config,
            "description": variant.description,
            "created_by": variant.created_by,
            "created_at": format_iso_utc(variant.created_at),
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

        console.print("[green]实验分组详情[/green]\n")

        console.print(f"[cyan]{'VARIANT ID':<16}[/cyan] : {variant.variant_id}")
        console.print(f"[cyan]{'EXPERIMENT ID':<16}[/cyan] : {variant.experiment_id}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {variant.name}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {variant.deployment_id}")
        console.print(f"[cyan]{'WEIGHT':<16}[/cyan] : {variant.weight}")
        console.print(f"[cyan]{'CONTROL':<16}[/cyan] : {variant.is_control}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {variant.status}")
        console.print(f"[cyan]{'DESCRIPTION':<16}[/cyan] : {variant.description or '-'}")
        console.print(f"[cyan]{'CREATED BY':<16}[/cyan] : {variant.created_by or '-'}")
        console.print(f"[cyan]{'CREATED AT':<16}[/cyan] : {format_datetime(variant.created_at)}")
        console.print(f"[cyan]{'UPDATED AT':<16}[/cyan] : {format_datetime(variant.updated_at)}")

        if variant.config:
            console.print(
                f"[cyan]{'CONFIG':<16}[/cyan] : "
                f"{json.dumps(variant.config, ensure_ascii=False)}"
            )

        return result

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())