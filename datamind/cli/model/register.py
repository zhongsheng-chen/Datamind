"""注册模型命令.

提供模型注册功能。

核心功能：
  - register_model: 注册模型

使用示例：
  python -m datamind.cli.main model register scorecard \
    --version 1.0.0 \
    --display-name "信用评分卡模型" \
    --model-path scorecard.pkl \
    --framework sklearn \
    --model-type logistic_regression \
    --task-type scoring \
    --description "信用评分卡模型" \
    --version-description "信用评分卡模型 v1.0.0"
"""

import asyncio
import json

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.errors import ModelError
from datamind.services.registration import ModelRegistrationService

app = typer.Typer(help="注册模型命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("register")
def register_model(
        name: str = typer.Argument(
            ...,
            help="模型名称"
        ),
        version: str = typer.Option(
            ...,
            "--version",
            help="模型版本"
        ),
        display_name: str | None = typer.Option(
            None,
            "--display-name",
            help="模型显示名称"
        ),
        model_path: str = typer.Option(
            ...,
            "--model-path",
            help="模型文件路径"
        ),
        framework: str = typer.Option(
            ...,
            "--framework",
            help="模型框架"
        ),
        model_type: str = typer.Option(
            ...,
            "--model-type",
            help="模型类型"
        ),
        task_type: str = typer.Option(
            ...,
            "--task-type",
            help="任务类型"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="模型描述"
        ),
        version_description: str | None = typer.Option(
            None,
            "--version-description",
            help="模型版本描述"
        ),
        force: bool = typer.Option(
            False,
            "--force",
            help=(
                "为未启用且从未部署的已有版本"
                "注册新的制品修订"
            )
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """注册模型."""

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=lambda p, r: r["model_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in (
                "text",
                "json",
        ):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始注册模型",
            name=name,
            version=version,
            framework=framework,
            model_type=model_type,
            task_type=task_type,
            force=force,
        )

        register = ModelRegistrationService()

        try:
            result = await register.register(
                name=name,
                version=version,
                framework=framework,
                model_type=model_type,
                task_type=task_type,
                model_path=model_path,
                display_name=display_name,
                description=description,
                version_description=version_description,
                created_by=actor,
                force=force,
            )
        except (
            ModelError,
            ValueError,
        ) as exc:
            console.error(
                f"模型注册失败：{exc}",
                output_format=output,
                error_type=type(exc).__name__,
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

        console.info("模型注册成功\n")

        console.print(
            f"{'MODEL ID':<16} : "
            f"{result['model_id']}"
        )
        console.print(
            f"{'VERSION ID':<16} : "
            f"{result['version_id']}"
        )
        console.print(
            f"{'NAME':<16} : "
            f"{result['name']}"
        )
        console.print(
            f"{'VERSION':<16} : "
            f"{result['version']}"
        )
        console.print(
            f"{'BENTO TAG':<16} : "
            f"{result['bento_tag']}"
        )
        console.print(
            f"{'ARTIFACT ID':<16} : "
            f"{result['artifact_id']}"
        )
        console.print(
            f"{'REVISION':<16} : "
            f"{result['artifact_revision']}"
        )
        console.print(
            f"{'ACTION':<16} : "
            f"{result['action']}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="model.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
