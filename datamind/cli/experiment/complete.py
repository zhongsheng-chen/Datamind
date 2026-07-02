# datamind/cli/experiment/complete.py

"""完成实验命令

提供实验完成标记功能。

核心功能：
  - complete_experiment: 完成实验

使用示例：
  python -m datamind.cli.main experiment complete exp_a1b2c3d4 --operator admin
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import ExperimentRepository
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="完成实验命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("complete")
def complete_experiment(
    experiment_id: str = typer.Argument(
        ...,
        help="实验 ID"
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
    """完成实验"""

    @audit(
        action="experiment.complete",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始完成实验",
            experiment_id=experiment_id,
        )

        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)

            experiment = await repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            repo.complete_experiment(
                experiment,
                updated_by=operator,
            )

            result = {
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "name": experiment.name,
                "status": experiment.status,
                "updated_by": experiment.updated_by,
                "updated_at": format_iso_utc(experiment.updated_at),
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

        console.print("[green]实验完成成功[/green]\n")
        console.print(f"[cyan]{'EXPERIMENT ID':<18}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'STATUS':<18}[/cyan] : {result['status']}")

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