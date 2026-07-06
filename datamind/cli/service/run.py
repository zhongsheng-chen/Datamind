# datamind/cli/service/run.py

"""运行服务命令

提供 Datamind Runtime Service 启动功能。

核心功能：
  - run_service: 启动模型服务

使用示例：
  python -m datamind.cli.main service run \
    --environment production \
    --host 0.0.0.0 \
    --port 3000 \
    --operator admin
"""

import asyncio
import os
import subprocess

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.config import get_settings

app = typer.Typer(help="运行服务命令")
console = Console()

logger = structlog.get_logger(__name__)

SERVICE_TARGET = (
    "datamind.runtime.server.service:"
    "DatamindRuntimeService"
)


@app.command("run")
def run_service(
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="运行环境，默认使用服务配置"
        ),
        host: str | None = typer.Option(
            None,
            "--host",
            help="监听地址，默认使用服务配置"
        ),
        port: int | None = typer.Option(
            None,
            "--port",
            help="监听端口，默认使用服务配置"
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="代码变更时自动重载"
        ),
        operator: str = typer.Option(
            "system",
            "--operator",
            help="操作人"
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="显示调试日志"
        ),
):
    """启动 Datamind 模型服务"""
    settings = get_settings()
    service_config = settings.service

    resolved_environment = (
        environment
        if environment is not None
        else service_config.environment
    )

    resolved_host = (
        host
        if host is not None
        else service_config.host
    )

    resolved_port = (
        port
        if port is not None
        else service_config.port
    )

    configured_service_name = service_config.name

    process: subprocess.Popen | None = None

    @audit(
        action="service.run",
        target_type="service",
        target_id_from="service_name",
    )
    async def _run(
            *,
            service_name: str,
            run_environment: str,
            run_host: str,
            run_port: int,
            reload_enabled: bool,
    ):
        nonlocal process

        if not run_environment:
            raise typer.BadParameter(
                "--environment 不能为空"
            )

        if not run_host:
            raise typer.BadParameter(
                "--host 不能为空"
            )

        if not 1 <= run_port <= 65535:
            raise typer.BadParameter(
                "--port 必须在 1 到 65535 之间"
            )

        command: list[str] = [
            "bentoml",
            "serve",
            SERVICE_TARGET,
            "--host",
            run_host,
            "--port",
            str(run_port),
        ]

        if reload_enabled:
            command.append("--reload")

        env = os.environ.copy()

        env["DATAMIND_SERVICE_ENVIRONMENT"] = (
            run_environment
        )

        logger.info(
            "开始启动 Datamind 模型服务",
            service_name=service_name,
            environment=run_environment,
            host=run_host,
            port=run_port,
            workers=service_config.workers,
            reload=reload_enabled,
            operator=operator,
        )

        try:
            started_process = subprocess.Popen(
                command,
                env=env,
            )

        except FileNotFoundError:
            console.print(
                "[red]未找到 bentoml 命令，"
                "请确认 BentoML 已正确安装[/red]"
            )
            raise typer.Exit(1)

        process = started_process

        result = {
            "name": service_name,
            "environment": run_environment,
            "host": run_host,
            "port": run_port,
            "workers": service_config.workers,
            "reload": reload_enabled,
            "pid": started_process.pid,
        }

        console.print(
            "[green]Datamind 模型服务启动成功[/green]\n"
        )

        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'HOST':<16}[/cyan] : {result['host']}")
        console.print(f"[cyan]{'PORT':<16}[/cyan] : {result['port']}")
        console.print(f"[cyan]{'WORKERS':<16}[/cyan] : {result['workers']}")
        console.print(f"[cyan]{'RELOAD':<16}[/cyan] : {result['reload']}")
        console.print(f"[cyan]{'PID':<16}[/cyan] : {result['pid']}")

        console.print()

        return result

    async def runner():
        async with cli_context(
                user=operator,
                source="cli",
                verbose=verbose,
                enable_audit=True,
        ):
            await _run(
                service_name=configured_service_name,
                run_environment=resolved_environment,
                run_host=resolved_host,
                run_port=resolved_port,
                reload_enabled=reload,
            )

    asyncio.run(runner())

    if process is None:
        raise typer.Exit(1)

    service_process = process

    try:
        return_code = service_process.wait()

        if return_code != 0:
            console.print(
                "[red]Datamind 模型服务异常退出，"
                f"退出码: {return_code}[/red]"
            )
            raise typer.Exit(return_code)

    except KeyboardInterrupt:
        service_process.terminate()
        service_process.wait()

        console.print(
            "\n[yellow]Datamind 模型服务已停止[/yellow]"
        )
