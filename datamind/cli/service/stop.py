# datamind/cli/service/stop.py

"""停止服务命令

提供模型运行时服务停止功能。

核心功能：
  - stop_service: 停止模型服务

使用示例：
  python -m datamind.cli.main service stop dep_a1b2c3d4 --operator admin
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="停止服务命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("stop")
def stop_service(
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
    """停止服务"""

    @audit(
        action="service.stop",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始停止模型服务",
            deployment_id=deployment_id,
        )

        manager = RuntimeManager()

        try:
            runtime_model = await manager.stop(
                deployment_id=deployment_id,
                operator=operator,
            )
        except RuntimeRouteError as e:
            message = getattr(e, "message", str(e))
            console.print(f"[red]{message}[/red]")
            raise typer.Exit(1)

        result = {
            "deployment_id": deployment_id,
            "stopped": runtime_model is not None,
        }

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

        if runtime_model is None:
            console.print(f"[yellow]模型服务未加载: {deployment_id}[/yellow]")
        else:
            console.print("[green]模型服务停止成功[/green]\n")
            console.print(f"[cyan]{'DEPLOYMENT ID':<18}[/cyan] : {deployment_id}")

        return result

    async def runner():
        async with cli_context(
            user=operator,
            source="cli",
            verbose=verbose,
            enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())