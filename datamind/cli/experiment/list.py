# datamind/cli/experiment/list.py

"""列出实验命令

提供实验列表查询功能。

核心功能：
  - list_experiments: 列出实验

使用示例：
  python -m datamind.cli.main experiment list
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
    model_id: str | None = typer.Option(
        None,
        "--model-id",
        help="按模型 ID 过滤"
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="按实验状态过滤，例如 draft/running/paused/stopped/completed/archived"
    ),
    created_by: str | None = typer.Option(
        None,
        "--created-by",
        help="按创建人过滤"
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="返回记录数量限制"
    ),
    offset: int | None = typer.Option(
        None,
        "--offset",
        help="分页偏移量"
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

        filters = {}

        if model_id is not None:
            filters["model_id"] = model_id

        if status is not None:
            filters["status"] = status

        if created_by is not None:
            filters["created_by"] = created_by

        logger.info(
            "开始列出实验",
            model_id=model_id,
            status=status,
            created_by=created_by,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)

            experiments = await repo.list_experiments(
                limit=limit,
                offset=offset,
                **filters,
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
        table.add_column("BUCKET KEY")
        table.add_column("UPDATED AT")

        for exp in experiments:
            traffic_ratio = "-"
            bucket_key = "-"

            if isinstance(exp.config, dict):
                traffic_ratio = str(exp.config.get("traffic_ratio", "-"))
                bucket_key = str(exp.config.get("bucket_key", "-"))

            table.add_row(
                exp.experiment_id,
                exp.model_id,
                exp.name or "-",
                exp.status,
                traffic_ratio,
                bucket_key,
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