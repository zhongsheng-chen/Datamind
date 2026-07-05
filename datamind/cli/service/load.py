# datamind/cli/service/load.py

"""加载服务命令

提供部署模型加载请求功能。

核心功能：
  - load_service: 请求加载部署模型

使用示例：
  python -m datamind.cli.main service load dep_a1b2c3d4
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services.runtime import RuntimeController

app = typer.Typer(help="加载服务命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("load")
def load_service(
    deployment_id: str = typer.Argument(
        ...,
        help="部署 ID"
    ),
    operator: str = typer.Option(
        "system",
        "--operator",
        help="操作人"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示调试日志"
    ),
):
    """请求加载部署模型"""

    @audit(
        action="service.load",
        target_type="deployment",
        target_id_from="target_deployment_id",
    )
    async def _run(
        *,
        target_deployment_id: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始提交模型加载请求",
            deployment_id=target_deployment_id,
        )

        controller = RuntimeController()

        result = await controller.load(
            deployment_id=target_deployment_id,
            operator=operator,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return result

        control = result["control"]

        console.print(
            "[green]模型加载请求提交成功[/green]\n"
        )

        console.print(
            f"[cyan]{'CONTROL ID':<18}[/cyan] : "
            f"{control['control_id']}"
        )
        console.print(
            f"[cyan]{'DEPLOYMENT ID':<18}[/cyan] : "
            f"{control['deployment_id']}"
        )
        console.print(
            f"[cyan]{'DESIRED STATUS':<18}[/cyan] : "
            f"{control['desired_status']}"
        )
        console.print(
            f"[cyan]{'GENERATION':<18}[/cyan] : "
            f"{control['generation']}"
        )
        console.print(
            f"[cyan]{'ACCEPTED':<18}[/cyan] : "
            f"{result['accepted']}"
        )

        return result

    async def runner():
        async with cli_context(
            user=operator,
            source="cli",
            verbose=verbose,
            enable_audit=True,
        ):
            await _run(
                target_deployment_id=deployment_id,
            )

    asyncio.run(runner())