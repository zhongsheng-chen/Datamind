"""恢复实验分组命令

提供逻辑删除实验分组的恢复功能。

核心功能：
  - restore_variant: 恢复实验分组

使用示例：
  datamind experiment variant restore var_0123456789abcdef
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

app = typer.Typer(help="恢复实验分组命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("restore")
def restore_variant(
        variant_id: str = typer.Argument(
            ...,
            help="实验分组 ID",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """恢复逻辑删除的实验分组"""

    @audit(
        action="experiment.variant.restore",
        target_type="variant",
        target_id_func=lambda _p, result: result["variant_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始恢复实验分组",
            variant_id=variant_id,
        )
        result = await ExperimentLifecycleService().restore_variant(
            variant_id=variant_id,
            restored_by=actor,
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
            console.info("分组恢复成功\n")
            console.print(
                f"{'VARIANT ID':<18} : "
                f"{result['variant_id']}"
            )
            console.print(
                f"{'STATUS':<18} : "
                f"{result['status']}"
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
            f"分组恢复失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
