# datamind/cli/experiment/pause.py

"""暂停实验命令

提供实验暂停功能。

核心功能：
  - pause_experiment: 暂停实验

使用示例：
  python -m datamind.cli.main experiment pause exp_0123456789abcdef
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
from datamind.db.repositories import ExperimentRepository
from datamind.models.errors import ExperimentError
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="暂停实验命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("pause")
def pause_experiment(
        experiment_id: str = typer.Argument(
            ...,
            help="实验 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """暂停实验"""

    @audit(
        action="experiment.pause",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始暂停实验",
            experiment_id=experiment_id,
        )

        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)

            experiment = await repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            try:
                repo.pause_experiment(
                    experiment,
                    updated_by=actor,
                )

            except ExperimentError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc

            await uow.session.flush()
            await uow.session.refresh(experiment)

            result: dict[str, Any] = {
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
                )
            )
            return result

        console.print("[green]实验暂停成功[/green]\n")
        console.print(f"[cyan]{'EXPERIMENT ID':<18}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'STATUS':<18}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
