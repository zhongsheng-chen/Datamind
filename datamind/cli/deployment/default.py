"""默认部署管理命令.

显式设置或取消模型在运行环境中的默认流量目标。

核心功能：
  - set_default_deployment: 设置默认部署
  - unset_default_deployment: 取消默认部署
"""

import asyncio
import json

import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.models.errors import DeploymentError
from datamind.services.deployment import DeploymentLifecycleService

app = typer.Typer(help="默认部署管理命令")
console = CLIConsole()


@app.command("set-default")
def set_default_deployment(
        deployment_id: str = typer.Argument(..., help="部署 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """设置默认部署.

    默认部署必须是已启用且处于有效期内的 `champion`，设置后替换原默认部署。
    """
    @audit(
        action="deploy.set-default", target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def run(actor: str):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")
        try:
            result = await DeploymentLifecycleService().set_default_deployment(
                deployment_id=deployment_id, updated_by=actor,
            )
        except DeploymentError as error:
            console.error(str(error), output_format=output, error_type=type(error).__name__)
            raise typer.Exit(code=1) from None
        if output == "json":
            console.print_json(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            console.info("默认部署设置成功")
            console.print(f"DEPLOYMENT ID : {result['deployment_id']}")
        return result

    async def runner():
        async with cli_context(required_permission="deployment.write") as context:
            await run(context.user)

    asyncio.run(runner())

@app.command("unset-default")
def unset_default_deployment(
        deployment_id: str = typer.Argument(..., help="部署 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """取消默认部署.

    取消后，该部署仍可通过路由或定向请求接收流量。
    """
    @audit(
        action="deploy.unset-default", target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def run(actor: str):
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")
        try:
            result = await DeploymentLifecycleService().unset_default_deployment(
                deployment_id=deployment_id, updated_by=actor,
            )
        except DeploymentError as error:
            console.error(str(error), output_format=output, error_type=type(error).__name__)
            raise typer.Exit(code=1) from None
        if output == "json":
            console.print_json(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            console.info("默认部署取消成功")
            console.print(f"DEPLOYMENT ID : {result['deployment_id']}")
        return result

    async def runner():
        async with cli_context(required_permission="deployment.write") as context:
            await run(context.user)

    asyncio.run(runner())
