"""删除实验命令

提供实验逻辑删除功能。

核心功能：
  - delete_experiment: 删除实验

使用示例：
  datamind experiment delete exp_0123456789abcdef --yes
"""

import asyncio
import json

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.errors import ExperimentError
from datamind.services.experiment import ExperimentLifecycleService

app = typer.Typer(help="删除实验命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_experiment(
        experiment_id: str = typer.Argument(
            ...,
            help="实验 ID",
        ),
        reason: str | None = typer.Option(
            None,
            "--reason",
            help="删除原因",
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="跳过确认",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """逻辑删除草稿或已归档实验及其分组"""

    @audit(
        action="experiment.delete",
        target_type="experiment",
        target_id_func=lambda _p, result: result["experiment_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if not yes:
            typer.confirm(
                f"确认删除实验 {experiment_id}？",
                abort=True,
            )

        logger.info(
            "开始删除实验",
            experiment_id=experiment_id,
        )
        result = await ExperimentLifecycleService().delete_experiment(
            experiment_id=experiment_id,
            reason=reason,
            deleted_by=actor,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            console.info("实验删除成功\n")
            console.print(
                f"{'EXPERIMENT ID':<18} : "
                f"{result['experiment_id']}"
            )
            console.print(
                f"{'VARIANTS':<18} : "
                f"{result['variant_count']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="experiment.delete",
        ) as context:
            await _run(context.user)

    try:
        asyncio.run(runner())
    except ExperimentError as error:
        console.error(
            f"实验删除失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
