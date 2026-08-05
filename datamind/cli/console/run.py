# datamind/cli/console/run.py

"""启动管理控制台命令

提供管理控制台启动功能。

核心功能：
  - run_console: 启动管理控制台

使用示例：
  python -m datamind.cli.main console run \
    --host 0.0.0.0 \
    --port 3100
"""

import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import structlog
import typer
from rich.console import Console

from datamind.cli.branding import (
    build_http_url,
    print_startup_summary,
)
from datamind.config import get_settings

app = typer.Typer(
    help="启动管理控制台命令"
)
console = Console()

logger = structlog.get_logger(__name__)

CONSOLE_TARGET = (
    "datamind.console.service:"
    "DatamindConsoleService"
)
_STARTUP_TIMEOUT_SECONDS = 30.0
_READY_CHECK_INTERVAL_SECONDS = 0.2
_READY_CHECK_TIMEOUT_SECONDS = 1.0


def _wait_until_ready(
        process: subprocess.Popen,
        access_url: str,
) -> bool:
    """等待管理控制台能够响应 HTTP 请求"""
    deadline = (
        time.monotonic()
        + _STARTUP_TIMEOUT_SECONDS
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False

        try:
            with urlopen(
                    access_url,
                    timeout=_READY_CHECK_TIMEOUT_SECONDS,
            ) as response:
                if response.status < 500:
                    return True

        except HTTPError as error:
            if error.code < 500:
                return True

        except (OSError, URLError):
            pass

        time.sleep(
            _READY_CHECK_INTERVAL_SECONDS
        )

    return False


@app.command("run")
def run_console(
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            help="监听地址",
        ),
        port: int = typer.Option(
            3100,
            "--port",
            help="监听端口",
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="代码变更时自动重载",
        ),
) -> None:
    """启动管理控制台"""
    normalized_host = host.strip()

    if normalized_host == "":
        raise typer.BadParameter(
            "--host 不能为空"
        )

    if not 1 <= port <= 65535:
        raise typer.BadParameter(
            "--port 必须在 1 到 65535 之间"
        )

    environment = (
        get_settings().service.environment
    )

    command = [
        sys.executable,
        "-m",
        "bentoml",
        "serve",
        CONSOLE_TARGET,
        "--host",
        normalized_host,
        "--port",
        str(port),
    ]

    if reload:
        command.append(
            "--reload"
        )

    access_url = build_http_url(
        host=normalized_host,
        port=port,
    )
    readiness_url = build_http_url(
        host=normalized_host,
        port=port,
        path="/health",
    )

    logger.info(
        "管理控制台启动",
        host=normalized_host,
        port=port,
        reload=reload,
        service_target=CONSOLE_TARGET,
    )

    try:
        process = subprocess.Popen(
            command
        )
    except OSError as exc:
        logger.error(
            "管理控制台启动失败",
            host=normalized_host,
            port=port,
            error=str(exc),
        )
        console.print(
            "[red]管理控制台启动失败："
            "无法启动 BentoML[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None

    print_startup_summary(
        console,
        {
            "NAME": "datamind",
            "ENVIRONMENT": environment,
            "HOST": normalized_host,
            "PORT": port,
            "RELOAD": reload,
            "PID": process.pid,
        },
    )

    try:
        if not _wait_until_ready(
                process,
                readiness_url,
        ):
            return_code = process.poll()

            if return_code is None:
                process.terminate()
                process.wait()
                logger.error(
                    "管理控制台启动超时",
                    host=normalized_host,
                    port=port,
                )
                console.print(
                    "[red]管理控制台启动失败："
                    "等待服务就绪超时[/red]"
                )
                raise typer.Exit(
                    code=1
                )

            logger.error(
                "管理控制台启动前异常退出",
                host=normalized_host,
                port=port,
                return_code=return_code,
            )
            raise typer.Exit(
                code=return_code or 1
            )

        console.print(
            "访问地址："
            f"[cyan]{access_url}[/cyan]"
        )
        console.print(
            "按 Ctrl+C 停止\n"
        )

        return_code = process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return_code = process.wait()
        logger.info(
            "管理控制台已停止",
            host=normalized_host,
            port=port,
            return_code=return_code,
        )
        console.print(
            "\n[yellow]管理控制台已停止[/yellow]"
        )
        return

    if return_code == 0:
        logger.info(
            "管理控制台进程已退出",
            host=normalized_host,
            port=port,
            return_code=return_code,
        )
        return

    logger.error(
        "管理控制台异常退出",
        host=normalized_host,
        port=port,
        return_code=return_code,
    )
    raise typer.Exit(
        code=return_code
    )
