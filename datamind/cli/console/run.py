"""启动管理控制台命令.

提供管理控制台启动功能。

核心功能：
  - run_console: 启动管理控制台
  - wait_for_console_ready: 等待控制台就绪
  - stop_console_process: 停止本次启动的控制台进程树

使用示例：
  python -m datamind.cli.main console run \
    --host 0.0.0.0 \
    --port 8701
"""

import os
import signal
import subprocess
import sys
import time
import uuid
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

# 进程清理命令及退出等待的单次超时时间（秒）
_STOP_TIMEOUT_SECONDS = 10

# 就绪探测失败后的重试间隔（秒）
_READY_CHECK_INTERVAL_SECONDS = 0.2

# 就绪探测连接的套接字操作超时时间（秒）
_READY_CHECK_TIMEOUT_SECONDS = 1.0


def wait_for_console_ready(
        process: subprocess.Popen,
        access_url: str,
        *,
        timeout_seconds: float,
) -> bool:
    """等待管理控制台通过 BentoML 就绪探测."""
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
        + timeout_seconds
    )
    last_failure = "尚未建立连接"

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

            last_failure = (
                "HTTP 状态码 "
                f"{response.status}"
            )

        except (HTTPException, OSError) as exc:
            last_failure = (
                f"{type(exc).__name__}: {exc}"
            )

        finally:
            connection.close()

        time.sleep(
            _READY_CHECK_INTERVAL_SECONDS
        )

    logger.warning(
        "Datamind 管理控制台就绪探测超时",
        readiness_url=access_url,
        timeout_seconds=timeout_seconds,
        last_failure=last_failure,
    )
    return False


def stop_console_process(
        process: subprocess.Popen,
) -> bool:
    """停止当前命令创建的进程树，并有界等待退出."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=True,
                capture_output=True,
                timeout=_STOP_TIMEOUT_SECONDS,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)

        try:
            process.wait(timeout=_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                raise
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=_STOP_TIMEOUT_SECONDS)

        if sys.platform != "win32":
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error(
            "Datamind 管理控制台进程树清理失败",
            pid=process.pid,
            error_type=type(exc).__name__,
        )
        return False

    return True


@app.command("run")
def run_console(
        host: str | None = typer.Option(
            None,
            "--host",
            help="监听地址，默认 127.0.0.1",
        ),
        port: int | None = typer.Option(
            None,
            "--port",
            help="监听端口，默认 8701",
        ),
        startup_timeout: int | None = typer.Option(
            None,
            "--startup-timeout",
            min=1,
            max=600,
            help="等待控制台就绪的最长时间（秒），默认 120",
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="代码变更时自动重载",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="显示 BentoML 警告和信息日志",
        ),
) -> None:
    """启动管理控制台."""
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
    resolved_startup_timeout = (
        startup_timeout
        if startup_timeout is not None
        else console_config.startup_timeout
    )

    if normalized_host == "":
        raise typer.BadParameter(
            "--host 不能为空"
        )

    if not 1 <= resolved_port <= 65535:
        raise typer.BadParameter(
            "--port 必须在 1 到 65535 之间"
        )

    environment = settings.service.environment.value

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
        path="/ready",
    )
    app_version = get_app_version()
    listen_address = build_bind_address(
        host=normalized_host,
        port=resolved_port,
    )
    service_instance_id = uuid.uuid4().hex
    env = os.environ.copy()
    env["DATAMIND_SERVICE_INSTANCE_ID"] = service_instance_id
    started_at = time.monotonic()

    try:
        process = subprocess.Popen(
            command,
            env=env,
            start_new_session=sys.platform != "win32",
        )
    except OSError as exc:
        logger.error(
            "Datamind 管理控制台启动失败",
            service_instance_id=service_instance_id,
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
            "Datamind 管理控制台启动失败："
            "无法启动 BentoML"
        )
        raise typer.Exit(
            code=1
        ) from None

    startup_context = {
        "service_instance_id": service_instance_id,
        "service_name": CONSOLE_SERVICE_NAME,
        "version": app_version,
        "environment": environment,
        "bind": listen_address,
        "url": access_url,
        "reload": reload,
        "pid": process.pid,
    }
    logger.debug(
        "Datamind 管理控制台子进程已启动",
        verbose=verbose,
        service_target=CONSOLE_TARGET,
        **startup_context,
    )

    try:
        if not wait_for_console_ready(
                process,
                readiness_url,
                timeout_seconds=resolved_startup_timeout,
        ):
            return_code = process.poll()

            if return_code is None:
                elapsed_seconds = round(time.monotonic() - started_at, 2)
                cleanup_complete = stop_console_process(process)
                logger.error(
                    "Datamind 管理控制台启动超时",
                    timeout_seconds=resolved_startup_timeout,
                    elapsed_seconds=elapsed_seconds,
                    cleanup_complete=cleanup_complete,
                    **startup_context,
                )
                console.error(
                    "Datamind 管理控制台启动失败："
                    f"等待服务就绪超时（{resolved_startup_timeout} 秒）。"
                    "可使用 --startup-timeout 调整等待时间，"
                    "或使用 --verbose 查看启动日志。"
                )
                if not cleanup_complete:
                    console.error("后台进程清理失败，请检查本次启动的进程。")
                raise typer.Exit(
                    code=1
                )

            logger.error(
                "Datamind 管理控制台启动前异常退出",
                return_code=return_code,
                **startup_context,
            )
            raise typer.Exit(
                code=return_code or 1
            )

        logger.info(
            "Datamind 管理控制台启动完成",
            elapsed_seconds=round(time.monotonic() - started_at, 2),
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
        if not stop_console_process(process):
            console.error("Datamind 管理控制台停止失败，请检查后台进程。")
            raise typer.Exit(code=1) from None
        return_code = process.returncode
        logger.info(
            "Datamind 管理控制台已停止",
            return_code=return_code,
            **startup_context,
        )
        console.warning("\nDatamind 管理控制台已停止")
        return

    if return_code == 0:
        logger.info(
            "Datamind 管理控制台进程已退出",
            return_code=return_code,
            **startup_context,
        )
        return

    logger.error(
        "Datamind 管理控制台异常退出",
        return_code=return_code,
        **startup_context,
    )
    raise typer.Exit(
        code=return_code
    )
