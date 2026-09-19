"""禁用部署命令

提供部署禁用功能，并自动请求 Worker 停止运行实例。

核心功能：
  - disable_deployment: 禁用部署

使用示例：
  python -m datamind.cli.main deployment disable dep_0123456789abcdef
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

app = typer.Typer(help="停用部署并停止运行实例")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("disable")
def disable_deployment(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """停用部署并停止运行实例"""

    @audit(
        action="deploy.disable",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run(
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始禁用部署",
            deployment_id=deployment_id,
        )

        deployer = DeploymentLifecycleService()

        try:
            result = await deployer.disable_deployment(
                deployment_id=deployment_id,
                updated_by=actor,
            )
        except DeploymentError as error:
            logger.warning(
                "禁用部署失败",
                deployment_id=deployment_id,
                error=str(error),
            )
            console.error(
                f"部署禁用失败：{error}",
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

        console.info("部署禁用成功\n")

        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'MODEL ID':<16} : {result['model_id']}")
        console.print(f"{'VERSION ID':<16} : {result['version_id']}")
        console.print(f"{'ENVIRONMENT':<16} : {result['environment']}")
        console.print(f"{'STATUS':<16} : {result['status']}")

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
