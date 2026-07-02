# datamind/cli/experiment/show.py

"""查看实验命令

提供实验详情查看功能。

核心功能：
  - show_experiment: 查看实验详情

使用示例：
  python -m datamind.cli.main experiment show exp_a1b2c3d4
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
from datamind.db.repositories import ExperimentRepository, VariantRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="查看实验命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_experiment(
    experiment_id: str = typer.Argument(
        ...,
        help="实验 ID"
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
    """查看实验详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看实验详情",
            experiment_id=experiment_id,
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            experiment = await experiment_repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            variants = await variant_repo.list_variants(
                experiment_id=experiment_id,
            )

        result = {
            "experiment": {
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "name": experiment.name,
                "status": experiment.status,
                "config": experiment.config,
                "description": experiment.description,
                "effective_from": format_iso_utc(experiment.effective_from),
                "effective_to": format_iso_utc(experiment.effective_to),
                "created_by": experiment.created_by,
                "created_at": format_iso_utc(experiment.created_at),
                "updated_by": experiment.updated_by,
                "updated_at": format_iso_utc(experiment.updated_at),
            },
            "variants": [
                {
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
                }
                for item in variants
            ],
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

        console.print("[green]实验详情[/green]\n")

        console.print(f"[cyan]{'EXPERIMENT ID':<18}[/cyan] : {experiment.experiment_id}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {experiment.model_id}")
        console.print(f"[cyan]{'NAME':<18}[/cyan] : {experiment.name or '-'}")
        console.print(f"[cyan]{'STATUS':<18}[/cyan] : {experiment.status}")
        console.print(f"[cyan]{'DESCRIPTION':<18}[/cyan] : {experiment.description or '-'}")
        console.print(f"[cyan]{'CREATED BY':<18}[/cyan] : {experiment.created_by or '-'}")
        console.print(f"[cyan]{'CREATED AT':<18}[/cyan] : {format_datetime(experiment.created_at)}")
        console.print(f"[cyan]{'UPDATED AT':<18}[/cyan] : {format_datetime(experiment.updated_at)}")

        if experiment.config:
            console.print(
                f"[cyan]{'CONFIG':<18}[/cyan] : "
                f"{json.dumps(experiment.config, ensure_ascii=False)}"
            )

        console.print()
        console.print(f"[green]实验共包含 {len(variants)} 个分组[/green]\n")

        if variants:
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

            for item in variants:
                table.add_row(
                    item.variant_id,
                    item.name,
                    item.deployment_id,
                    str(item.weight),
                    str(item.is_control),
                    item.status,
                )

            console.print(table)

        return result

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())