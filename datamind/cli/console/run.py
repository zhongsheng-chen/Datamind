# datamind/cli/console/run.py

"""启动管理控制台命令

提供管理控制台启动功能。

核心功能：
  - run_console: 启动管理控制台

使用示例：
  python -m datamind.cli.main console run \
    --host 0.0.0.0 \
    --port 8701
"""

import subprocess
import sys
import time
from http.client import (
    HTTPConnection,
    HTTPException,
)
from urllib.parse import urlsplit

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.cli.branding import (
    build_bind_address,
    build_http_url,
    get_app_version,
    print_http_server_summary,
)
from datamind.config import get_settings

app = typer.Typer(
    help="启动管理控制台命令"
)
console = CLIConsole()

logger = structlog.get_logger(__name__)

CONSOLE_TARGET = (
    "datamind.console.service:"
    "DatamindConsoleService"
)
CONSOLE_SERVICE_NAME = "datamind_console_service"
_STARTUP_TIMEOUT_SECONDS = 30.0
_READY_CHECK_INTERVAL_SECONDS = 0.2
_READY_CHECK_TIMEOUT_SECONDS = 1.0


def wait_for_console_ready(
        process: subprocess.Popen,
        access_url: str,
) -> bool:
    """等待管理控制台能够响应 HTTP 请求"""
    parsed_url = urlsplit(
        access_url
    )
    host = parsed_url.hostname

    if host is None:
        return False

    path = parsed_url.path or "/"

    if parsed_url.query:
        path = (
            f"{path}?{parsed_url.query}"
        )

    deadline = (
        time.monotonic()
        + _STARTUP_TIMEOUT_SECONDS
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False

        connection = HTTPConnection(
            host=host,
            port=parsed_url.port,
            timeout=_READY_CHECK_TIMEOUT_SECONDS,
        )

        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            response.read()

            if response.status == 200:
                return True

        except (HTTPException, OSError):
            pass

        finally:
            connection.close()

        time.sleep(
            _READY_CHECK_INTERVAL_SECONDS
        )

    return False


@app.command("run")
def run_console(
        host: str | None = typer.Option(
            None,
            "--host",
            help="监听地址，未指定时读取控制台配置",
        ),
        port: int | None = typer.Option(
            None,
            "--port",
            help="监听端口，未指定时读取控制台配置",
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="代码变更时自动重载",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="显示 BentoML 运行日志",
        ),
) -> None:
    """启动管理控制台"""
    settings = get_settings()
    console_config = settings.console
    resolved_host = (
        host
        if host is not None
        else console_config.host
    )
    resolved_port = (
        port
        if port is not None
        else console_config.port
    )
    normalized_host = resolved_host.strip()

    if normalized_host == "":
        raise typer.BadParameter(
            "--host 不能为空"
        )

    if not 1 <= resolved_port <= 65535:
        raise typer.BadParameter(
            "--port 必须在 1 到 65535 之间"
        )

    environment = settings.service.environment

    command = [
        sys.executable,
        "-m",
        "bentoml",
        "serve",
        CONSOLE_TARGET,
        "--host",
        normalized_host,
        "--port",
        str(resolved_port),
    ]

    if reload:
        command.append(
            "--reload"
        )

    if not verbose:
        command.append(
            "--quiet"
        )

    access_url = build_http_url(
        host=normalized_host,
        port=resolved_port,
    )
    readiness_url = build_http_url(
        host=normalized_host,
        port=resolved_port,
        path="/health",
    )
    app_version = get_app_version()
    listen_address = build_bind_address(
        host=normalized_host,
        port=resolved_port,
    )
    try:
        process = subprocess.Popen(
            command
        )
    except OSError as exc:
        logger.error(
            "管理控制台启动失败",
            service_name=CONSOLE_SERVICE_NAME,
            version=app_version,
            environment=environment,
            bind=listen_address,
            url=access_url,
            reload=reload,
            verbose=verbose,
            service_target=CONSOLE_TARGET,
            error=str(exc),
        )
        console.error(
            "管理控制台启动失败："
            "无法启动 BentoML"
        )
        raise typer.Exit(
            code=1
        ) from None

    startup_context = {
        "service_name": CONSOLE_SERVICE_NAME,
        "version": app_version,
        "environment": environment,
        "bind": listen_address,
        "url": access_url,
        "reload": reload,
        "pid": process.pid,
    }
    logger.debug(
        "管理控制台子进程已启动",
        verbose=verbose,
        service_target=CONSOLE_TARGET,
        **startup_context,
    )

    try:
        if not wait_for_console_ready(
                process,
                readiness_url,
        ):
            return_code = process.poll()

            if return_code is None:
                process.terminate()
                process.wait()
                logger.error(
                    "管理控制台启动超时",
                    **startup_context,
                )
                console.error(
                    "管理控制台启动失败："
                    "等待服务就绪超时"
                )
                raise typer.Exit(
                    code=1
                )

            logger.error(
                "管理控制台启动前异常退出",
                return_code=return_code,
                **startup_context,
            )
            raise typer.Exit(
                code=return_code or 1
            )

        logger.info(
            "管理控制台启动完成",
            **startup_context,
        )
        print_http_server_summary(
            console,
            app_version=app_version,
            environment=environment,
            bind_address=listen_address,
            access_url=access_url,
            reload_enabled=reload,
            pid=process.pid,
        )
        console.print(
            "Press Ctrl+C to stop\n"
        )

        return_code = process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return_code = process.wait()
        logger.info(
            "管理控制台已停止",
            return_code=return_code,
            **startup_context,
        )
        console.warning("\n管理控制台已停止")
        return

    if return_code == 0:
        logger.info(
            "管理控制台进程已退出",
            return_code=return_code,
            **startup_context,
        )
        return

    logger.error(
        "管理控制台异常退出",
        return_code=return_code,
        **startup_context,
    )
    raise typer.Exit(
        code=return_code
    )
