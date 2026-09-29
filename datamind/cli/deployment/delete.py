"""删除部署命令.

提供部署逻辑删除功能。

核心功能：
  - delete_deployment: 删除部署

使用示例：
  datamind deployment delete dep_0123456789abcdef --yes
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

app = typer.Typer(help="删除部署命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_deployment(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID",
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
    """逻辑删除已停用且已卸载的部署."""

    @audit(
        action="deployment.delete",
        target_type="deployment",
        target_id_func=lambda _p, result: result["deployment_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if not yes:
            typer.confirm(
                f"确认删除部署 {deployment_id}？",
                abort=True,
            )

        logger.info(
            "开始删除部署",
            deployment_id=deployment_id,
        )
        result = await DeploymentLifecycleService().delete_deployment(
            deployment_id=deployment_id,
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
            console.info("部署删除成功\n")
            console.print(
                f"{'DEPLOYMENT ID':<16} : "
                f"{result['deployment_id']}"
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
            f"部署删除失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
