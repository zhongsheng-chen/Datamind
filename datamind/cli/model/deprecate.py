"""弃用模型命令

负责模型及模型版本的弃用。

核心功能：
  - deprecate_model: 弃用模型或指定模型版本

使用示例：
  python -m datamind.cli.main model deprecate scorecard
"""

import asyncio
import json
from typing import Any

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.models.errors import ModelError
from datamind.services import ModelLifecycleService

app = typer.Typer(help="弃用模型命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("deprecate")
def deprecate_model(
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
            help="模型版本号"
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
    """弃用模型或模型版本

    未指定版本时，同时弃用模型的全部 active、inactive 版本。
    """

    @audit(
        action="model.deprecate",
        target_type="model",
        target_id_func=lambda p, r: r["model_id"],
    )
    async def _run(
            actor: str,
    ) -> dict[str, Any]:
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

        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始弃用模型",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
        )
        lifecycle = ModelLifecycleService()

        try:
            result = await lifecycle.deprecate(
                name=name,
                model_id=model_id,
                version=version,
                version_id=version_id,
                updated_by=actor,
            )
        except ModelError as error:
            console.error(
                f"模型弃用失败：{error}",
                output_format=output,
                error_type=type(error).__name__,
            )
            raise typer.Exit(code=1) from None

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.info("模型弃用成功\n")
        console.print(
            f"{'MODEL ID':<16} : "
            f"{result['model_id']}"
        )
        console.print(
            f"{'NAME':<16} : "
            f"{result['name']}"
        )
        console.print(
            f"{'MODEL STATUS':<16} : "
            f"{result['model_status']}"
        )
        if result.get("version_id"):
            console.print(
                f"{'VERSION ID':<16} : "
                f"{result['version_id']}"
            )
            console.print(
                f"{'VERSION':<16} : "
                f"{result['version']}"
            )
            console.print(
                f"{'VERSION STATUS':<16} : "
                f"{result['version_status']}"
            )
        else:
            console.print(
                f"{'VERSION CHANGES':<16} : "
                f"{result['deprecated_version_count']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="model.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(
        runner()
    )
