# datamind/cli/model/restore.py

"""恢复模型命令

提供模型或模型版本的逻辑删除恢复功能。

核心功能：
  - restore_model: 恢复模型或模型版本

使用示例：
  python -m datamind.cli.main model restore scorecard
"""

import asyncio
import json

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.models.errors import ModelError
from datamind.services import ModelDeletionService

app = typer.Typer(help="恢复模型命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


def _validate_target(
        *,
        name: str | None,
        model_id: str | None,
        version: str | None,
        version_id: str | None,
        output: str,
) -> None:
    """校验模型恢复目标和输出格式"""
    if not (name or model_id):
        raise typer.BadParameter(
            "必须提供 <name> 或 --model-id"
        )

    if name and model_id:
        raise typer.BadParameter(
            "<name> 与 --model-id 只能指定一个"
        )

    if version and version_id:
        raise typer.BadParameter(
            "--version 与 --version-id 只能指定一个"
        )

    if output not in {"text", "json"}:
        raise typer.BadParameter(
            "--format 只支持 text 或 json"
        )


@app.command("restore")
def restore_model(
        name: str | None = typer.Argument(
            None,
            help="模型名称"
        ),
        model_id: str | None = typer.Option(
            None,
            "--model-id",
            help="模型 ID"
        ),
        version: str | None = typer.Option(
            None,
            "--version",
            help="版本号"
        ),
        version_id: str | None = typer.Option(
            None,
            "--version-id",
            help="版本 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
) -> None:
    """恢复逻辑删除的模型或模型版本"""

    @audit(
        action="model.restore",
        target_type="model",
        target_id_func=lambda _p, result: (
            result.get("version_id") or result["model_id"]
        ),
    )
    async def _run(
            actor: str,
    ) -> dict:
        _validate_target(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            output=output,
        )

        logger.info(
            "开始恢复模型",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
        )

        result = await ModelDeletionService().restore(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            operator=actor,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2
                )
            )
        else:
            console.info("模型恢复成功")
            console.print(
                f"{'MODEL ID':<16} : "
                f"{result['model_id']}"
            )
            console.print(
                f"{'ACTION':<16} : "
                f"{result['action']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="model.write",
        ) as context:
            await _run(
                context.user
            )

    try:
        asyncio.run(
            runner()
        )
    except ModelError as error:
        console.error(
            f"模型恢复失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
