# datamind/cli/service/restart.py

"""重启服务命令

提供模型运行时服务重启功能。

核心功能：
  - restart_service: 重启模型服务

使用示例：
  python -m datamind.cli.main service restart dep_a1b2c3d4 --operator admin
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    RuntimeRouteError,
    VersionNotFoundError,
)
from datamind.runtime.manager import RuntimeManager

app = typer.Typer(help="重启服务命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("restart")
def restart_service(
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
    """重启服务"""

    @audit(
        action="service.restart",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始重启模型服务",
            deployment_id=deployment_id,
        )

        manager = RuntimeManager()

        try:
            runtime_model = await manager.restart(
                deployment_id=deployment_id,
                operator=operator,
            )
        except (
            BackendError,
            DeploymentNotFoundError,
            InvalidDeploymentStateError,
            RuntimeRouteError,
            VersionNotFoundError,
        ) as e:
            message = getattr(e, "message", str(e))
            console.print(f"[red]{message}[/red]")
            raise typer.Exit(1)

        result = runtime_model.to_dict()
        metadata = result.get("metadata") or {}

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

        console.print("[green]模型服务重启成功[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<18}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<18}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'FRAMEWORK':<18}[/cyan] : {result['framework']}")
        console.print(f"[cyan]{'BENTO TAG':<18}[/cyan] : {metadata.get('bento_tag') or '-'}")
        console.print(f"[cyan]{'WORKER':<18}[/cyan] : {metadata.get('worker_id') or '-'}")

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