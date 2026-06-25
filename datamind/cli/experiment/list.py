# datamind/cli/experiment/list.py

"""列出实验命令

提供实验列表查询功能。

核心功能：
  - list_experiments: 列出实验

使用示例：
  python -m datamind.cli.main experiment list --model-id mdl_a1b2c3d4
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
from datamind.db.repositories import ExperimentRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="列出实验命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_experiments(
    model_id: str = typer.Option(
        ...,
        "--model-id",
        help="模型 ID"
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
    """列出实验"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始列出实验",
            model_id=model_id,
        )

        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)

            experiments = await repo.list_experiments(
                model_id=model_id,
            )

        if output == "json":
            result = []

            for exp in experiments:
                result.append({
                    "experiment_id": exp.experiment_id,
                    "model_id": exp.model_id,
                    "name": exp.name,
                    "status": exp.status,
                    "config": exp.config,
                    "description": exp.description,
                    "effective_from": format_iso_utc(exp.effective_from),
                    "effective_to": format_iso_utc(exp.effective_to),
                    "created_by": exp.created_by,
                    "created_at": format_iso_utc(exp.created_at),
                    "updated_by": exp.updated_by,
                    "updated_at": format_iso_utc(exp.updated_at),
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

        console.print(f"[dim]共找到 {len(experiments)} 个实验[/dim]\n")

        if not experiments:
            return experiments

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("EXPERIMENT ID")
        table.add_column("MODEL ID")
        table.add_column("NAME")
        table.add_column("STATUS")
        table.add_column("TRAFFIC")
        table.add_column("UPDATED AT")

        for exp in experiments:
            traffic_ratio = "-"

            if isinstance(exp.config, dict):
                traffic_ratio = str(exp.config.get("traffic_ratio", "-"))

            table.add_row(
                exp.experiment_id,
                exp.model_id,
                exp.name or "-",
                exp.status,
                traffic_ratio,
                format_datetime(exp.updated_at),
            )

        console.print(table)

        return experiments

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())