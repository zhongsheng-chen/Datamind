"""删除模型命令

提供可恢复的模型逻辑删除功能。

核心功能：
  - delete_model: 删除模型

使用示例：
  python -m datamind.cli.main model delete scorecard \
    --version 1.0.0 \
    --yes
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

app = typer.Typer(help="删除模型命令")
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
    """校验模型删除目标和输出格式"""
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


@app.command("delete")
def delete_model(
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
            help="版本号（可选）"
        ),
        version_id: str | None = typer.Option(
            None,
            "--version-id",
            help="版本 ID（可选）"
        ),
        reason: str | None = typer.Option(
            None,
            "--reason",
            help="删除原因"
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="跳过确认"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """删除模型"""

    @audit(
        action="model.delete",
        target_type="model",
        target_id_func=lambda p, r: (
                r.get("version_id")
                if r.get("action") == "delete_version"
                else r.get("model_id")
        ),
    )
    async def _run(
            actor: str,
    ):
        _validate_target(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            output=output,
        )

        if not yes:
            if not typer.confirm("确认执行删除操作？"):
                raise typer.Exit(0)

        logger.info(
            "开始删除模型",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
        )

        deleter = ModelDeletionService()

        result = await deleter.delete(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            reason=reason,
            operator=actor,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        if result["action"] == "delete_version":
            console.info("模型版本删除成功\n")
            console.print(f"{'VERSION ID':<16} : {result['version_id']}")
            console.print(f"{'VERSION':<16} : {result['version']}")
            console.print(f"{'MODEL ID':<16} : {result['model_id']}")
        else:
            console.info("模型删除成功\n")
            console.print(f"{'MODEL ID':<16} : {result['model_id']}")
            console.print(f"{'NAME':<16} : {result['name']}")

        console.print(
            f"{'DELETION ID':<16} : "
            f"{result['deletion_id']}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="model.delete",
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
            f"模型删除失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
