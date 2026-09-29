"""恢复部署命令.

提供逻辑删除部署的恢复功能。

核心功能：
  - restore_deployment: 恢复部署

使用示例：
  datamind deployment restore dep_0123456789abcdef
"""

import asyncio
import json

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.models.errors import DeploymentError
from datamind.services.deployment import DeploymentLifecycleService

app = typer.Typer(help="恢复部署命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("restore")
def restore_deployment(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """恢复逻辑删除的部署."""

    @audit(
        action="deployment.restore",
        target_type="deployment",
        target_id_func=lambda _p, result: result["deployment_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始恢复部署",
            deployment_id=deployment_id,
        )
        result = await DeploymentLifecycleService().restore_deployment(
            deployment_id=deployment_id,
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
            console.info("部署恢复成功\n")
            console.print(
                f"{'DEPLOYMENT ID':<16} : "
                f"{result['deployment_id']}"
            )
            console.print(
                f"{'STATUS':<16} : "
                f"{result['status']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="deployment.delete",
        ) as context:
            await _run(context.user)

    try:
        asyncio.run(runner())
    except DeploymentError as error:
        console.error(
            f"部署恢复失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
