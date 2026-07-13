# datamind/cli/model/purge.py

"""永久清理模型制品命令

仅清理已经逻辑删除的模型或模型版本制品。

核心功能：
  - purge_model: 永久清理模型制品

使用示例：
  python -m datamind.cli.main model purge scorecard \
    --reason "模型已停止使用" \
    --yes
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services import ModelDeletionService

app = typer.Typer(help="永久清理模型制品命令")
console = Console()

logger = structlog.get_logger(__name__)


def _validate_target(
        *,
        name: str | None,
        model_id: str | None,
        version: str | None,
        version_id: str | None,
        output: str,
) -> None:
    """校验模型清理目标和输出格式"""
    if bool(name) == bool(model_id):
        raise typer.BadParameter(
            "必须且只能提供 <name> 或 --model-id"
        )

    if version and version_id:
        raise typer.BadParameter(
            "--version 与 --version-id 只能指定一个"
        )

    if output not in {"text", "json"}:
        raise typer.BadParameter(
            "--format 只支持 text 或 json"
        )


@app.command("purge")
def purge_model(
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
        reason: str = typer.Option(
            ...,
            "--reason",
            help="永久清理原因"
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="跳过不可逆操作确认"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
) -> None:
    """永久清理已逻辑删除的模型制品"""

    @audit(
        action="model.purge",
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

        if (
                not yes
                and not typer.confirm(
                    "该操作不可恢复，确认永久清理制品？"
                )
        ):
            raise typer.Exit(0)

        logger.info(
            "开始永久清理模型制品",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
        )

        result = await ModelDeletionService().purge(
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
                    indent=2
                )
            )
        else:
            color = "green" if result["failed_count"] == 0 else "yellow"
            console.print(
                f"[{color}]模型制品清理完成[/{color}]"
            )
            console.print(
                f"[cyan]{'PURGED':<16}[/cyan] : "
                f"{result['purged_count']}"
            )
            console.print(
                f"[cyan]{'FAILED':<16}[/cyan] : "
                f"{result['failed_count']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="model.delete",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(
        runner()
    )
