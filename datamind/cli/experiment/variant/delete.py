"""删除实验分组命令

提供实验分组逻辑删除功能。

核心功能：
  - delete_variant: 删除实验分组

使用示例：
  datamind experiment variant delete var_0123456789abcdef --yes
"""

import asyncio
import json

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.errors import ExperimentError
from datamind.services import ExperimentLifecycleService

app = typer.Typer(help="删除实验分组命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_variant(
        variant_id: str = typer.Argument(
            ...,
            help="实验分组 ID",
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
    """逻辑删除草稿实验中的分组"""

    @audit(
        action="experiment.variant.delete",
        target_type="variant",
        target_id_func=lambda _p, result: result["variant_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if not yes:
            typer.confirm(
                f"确认删除实验分组 {variant_id}？",
                abort=True,
            )

        logger.info(
            "开始删除实验分组",
            variant_id=variant_id,
        )
        result = await ExperimentLifecycleService().delete_variant(
            variant_id=variant_id,
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
            console.info("分组删除成功\n")
            console.print(
                f"{'VARIANT ID':<18} : "
                f"{result['variant_id']}"
            )
            console.print(
                f"{'EXPERIMENT ID':<18} : "
                f"{result['experiment_id']}"
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
            f"分组删除失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
