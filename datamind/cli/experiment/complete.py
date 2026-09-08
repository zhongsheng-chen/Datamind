"""完成实验命令

提供实验完成标记功能。

核心功能：
  - complete_experiment: 完成实验

使用示例：
  python -m datamind.cli.main experiment complete exp_0123456789abcdef
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
from datamind.db.repositories import ExperimentRepository
from datamind.models.errors import ExperimentError
from datamind.utils.datetime import format_iso_utc

app = typer.Typer(help="完成实验命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("complete")
def complete_experiment(
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
    """完成实验"""

    @audit(
        action="experiment.complete",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run(
            actor: str,
    ):
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
                console.error(
                    f"实验完成失败：实验不存在：{experiment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            try:
                repo.complete_experiment(
                    experiment,
                    updated_by=actor,
                )

            except ExperimentError as exc:
                console.error(
                    f"实验完成失败：{exc}",
                    output_format=output,
                    error_type=type(exc).__name__,
                )
                raise typer.Exit(code=1) from None

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

        console.info("实验完成\n")
        console.print(f"{'EXPERIMENT ID':<18} : {result['experiment_id']}")
        console.print(f"{'MODEL ID':<18} : {result['model_id']}")
        console.print(f"{'STATUS':<18} : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
