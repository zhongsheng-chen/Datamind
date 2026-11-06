"""运行预测服务命令.

提供预测服务启动功能。

核心功能：
  - run_service: 启动预测服务

使用示例：
  python -m datamind.cli.main service run \
    --host 0.0.0.0 \
    --port 8700
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from time import perf_counter
from types import FrameType
from typing import (
    Callable,
    TypedDict,
)

import structlog
import typer
from datamind.cli.branding import (
    build_bind_address,
    build_http_url,
    get_app_version,
    print_http_server_summary,
)
from datamind.cli.output import CLIConsole
from datamind.config import get_settings
from datamind.logging import (
    setup_logging,
    shutdown_logging,
)

app = typer.Typer(help="运行预测服务命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)

SERVICE_TARGET = (
    "datamind.runtime.server.service:"
    "DatamindRuntimeService"
)


class ServiceStartupResult(TypedDict):
    """预测服务启动结果."""

    name: str
    version: str
    environment: str
    bind: str
    url: str
    workers: int
    reload: bool
    pid: int


def _build_ready_dir(
        service_id: str,
) -> Path:
    """构建 Worker 就绪标记目录."""
    return (
        Path(tempfile.gettempdir())
        / "datamind"
        / "runtime_ready"
        / service_id
    )


def _prepare_ready_dir(
        ready_dir: Path,
) -> None:
    """准备 Worker 就绪标记目录."""
    shutil.rmtree(
        ready_dir,
        ignore_errors=True,
    )

    ready_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


def _cleanup_ready_dir(
        ready_dir: Path | None,
) -> None:
    """清理 Worker 就绪标记目录."""
    if ready_dir is None:
        return

    shutil.rmtree(
        ready_dir,
        ignore_errors=True,
    )


def _read_worker_ready_files(
        *,
        ready_dir: Path,
        service_id: str,
) -> set[str]:
    """读取已就绪 Worker."""
    worker_ids: set[str] = set()

    if not ready_dir.exists():
        return worker_ids

    for marker_path in ready_dir.glob("*.json"):
        try:
            record = json.loads(
                marker_path.read_text(
                    encoding="utf-8",
                ),
            )

        except (
                OSError,
                json.JSONDecodeError,
        ):
            continue

        if record.get("service_id") != service_id:
            continue

        if record.get("ready") is not True:
            continue

        worker_id = record.get(
            "worker_id",
        )

        if not worker_id:
            continue

        worker_ids.add(
            str(worker_id),
        )

    return worker_ids


async def _wait_for_workers_ready(
        *,
        ready_dir: Path,
        service_id: str,
        process: subprocess.Popen,
        expected_workers: int,
        timeout_seconds: float = 60.0,
        interval_seconds: float = 0.5,
        should_stop: Callable[[], bool] | None = None,
) -> set[str]:
    """等待全部 Worker 就绪."""
    loop = asyncio.get_running_loop()

    deadline = (
        loop.time()
        + timeout_seconds
    )

    last_worker_ids: tuple[str, ...] | None = None

    while True:
        if should_stop is not None and should_stop():
            raise asyncio.CancelledError

        return_code = process.poll()

        if return_code is not None:
            raise RuntimeError(
                "运行时服务子进程提前退出，"
                f"退出码: {return_code}",
            )

        ready_workers = _read_worker_ready_files(
            ready_dir=ready_dir,
            service_id=service_id,
        )

        current_worker_ids = tuple(
            sorted(ready_workers),
        )

        if current_worker_ids != last_worker_ids:
            logger.debug(
                "正在等待运行时 Worker 就绪",
                service_id=service_id,
                ready_dir=str(ready_dir),
                expected_workers=expected_workers,
                ready_workers=len(ready_workers),
                worker_ids=list(current_worker_ids),
            )

            last_worker_ids = current_worker_ids

        if len(ready_workers) >= expected_workers:
            return ready_workers

        if loop.time() >= deadline:
            raise TimeoutError(
                "等待运行时 Worker 启动超时: "
                f"ready_workers={len(ready_workers)}, "
                f"expected_workers={expected_workers}, "
                f"ready_dir={ready_dir}",
            )

        await asyncio.sleep(
            interval_seconds,
        )


async def _wait_for_process_exit(
        process: subprocess.Popen,
        should_stop: Callable[[], bool],
) -> int | None:
    """等待子进程退出."""
    while not should_stop():
        return_code = process.poll()

        if return_code is not None:
            return return_code

        await asyncio.sleep(
            0.1,
        )

    return None


def _wait_for_worker_shutdown(
        process: subprocess.Popen,
        ready_dir: Path,
        expected_workers: int,
        timeout_seconds: float = 30.0,
) -> bool:
    """等待 Worker 关闭."""
    ready_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    expected_worker_ids = {
        marker.stem
        for marker in ready_dir.glob("*.json")
    }

    (ready_dir / "stop.request").touch()

    deadline = time.monotonic() + timeout_seconds

    while True:
        stopped_worker_ids = {
            marker.stem
            for marker in ready_dir.glob("*.stopped")
        }

        if (
                len(stopped_worker_ids) >= expected_workers
                and expected_worker_ids <= stopped_worker_ids
        ):
            return True

        if (
                process.poll() is not None
                or time.monotonic() >= deadline
        ):
            return False

        time.sleep(
            0.1,
        )


def _stop_service_process(
        process: subprocess.Popen,
        *,
        ready_dir: Path | None = None,
        expected_workers: int = 0,
) -> int | None:
    """停止预测服务进程树."""
    if sys.platform == "win32":
        if (
                ready_dir is not None
                and expected_workers > 0
                and process.poll() is None
        ):
            complete = _wait_for_worker_shutdown(
                process,
                ready_dir,
                expected_workers,
            )

            if not complete and process.poll() is None:
                logger.warning(
                    "运行时 Worker 停止超时，将强制清理进程树",
                    pid=process.pid,
                    expected_workers=expected_workers,
                    stopped_workers=len(list(ready_dir.glob("*.stopped"))),
                )

        try:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                check=True,
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

        except subprocess.CalledProcessError as error:
            if error.returncode != 128 or process.poll() is None:
                raise
    else:
        try:
            os.killpg(
                process.pid,
                signal.SIGTERM,
            )

        except ProcessLookupError:
            pass

    try:
        return process.wait(
            timeout=10,
        )

    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            raise

        try:
            os.killpg(
                process.pid,
                signal.SIGKILL,
            )

        except ProcessLookupError:
            pass

        return process.wait(
            timeout=10,
        )


@app.command("run")
def run_service(
        host: str | None = typer.Option(
            None,
            "--host",
            help="监听地址，默认 0.0.0.0",
        ),
        port: int | None = typer.Option(
            None,
            "--port",
            help="监听端口，默认 8700",
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="代码变更后自动重载",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="显示 BentoML 警告和信息日志",
        ),
):
    """启动 Datamind 预测服务."""
    settings = get_settings()

    setup_logging(
        settings.logging,
    )

    service_config = settings.service
    expected_workers = int(service_config.workers)

    environment = settings.common.environment.value
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
    ready_dir: Path | None = None
    service_id: str | None = None
    service_started = False
    stop_requested = False

    async def _start_service(
            *,
            service_name: str,
            run_environment: str,
            run_host: str,
            run_port: int,
            reload_enabled: bool,
    ) -> ServiceStartupResult:
        """启动预测服务子进程并等待 Worker 就绪."""
        nonlocal process
        nonlocal ready_dir
        nonlocal service_id
        nonlocal service_started

        if not run_environment:
            raise typer.BadParameter(
                "DATAMIND_ENVIRONMENT 不能为空",
            )

        if not run_host:
            raise typer.BadParameter(
                "--host 不能为空",
            )

        if not 1 <= run_port <= 65535:
            raise typer.BadParameter(
                "--port 必须在 1 到 65535 之间",
            )

        app_version = get_app_version()

        command: list[str] = [
            sys.executable,
            "-m",
            "datamind.cli.http_entrypoint",
            "serve",
            SERVICE_TARGET,
            "--host",
            run_host,
            "--port",
            str(run_port),
        ]

        if reload_enabled:
            command.append("--reload")

        if not verbose:
            command.append("--quiet")

        current_service_id: str = uuid.uuid4().hex

        current_ready_dir: Path = _build_ready_dir(
            current_service_id,
        )

        service_id = current_service_id
        ready_dir = current_ready_dir

        _prepare_ready_dir(
            current_ready_dir,
        )

        env = os.environ.copy()

        env["DATAMIND_ENVIRONMENT"] = (
            run_environment
        )

        env["DATAMIND_SERVICE_ID"] = (
            current_service_id
        )

        env["DATAMIND_SERVICE_READY_DIR"] = (
            str(current_ready_dir)
        )

        startup_started = perf_counter()

        print_http_server_summary(
            console,
            app_version=app_version,
            environment=run_environment,
            bind_address=build_bind_address(
                host=run_host,
                port=run_port,
            ),
            access_url=build_http_url(
                host=run_host,
                port=run_port,
            ),
            workers=expected_workers,
            reload_enabled=reload_enabled,
        )
        logger.info("正在启动运行时服务，等待 Worker 就绪")

        try:
            started_process = subprocess.Popen(
                command,
                env=env,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
                start_new_session=sys.platform != "win32",
            )

        except FileNotFoundError:
            _cleanup_ready_dir(
                current_ready_dir,
            )

            logger.error(
                "运行时服务启动失败",
                service_name=service_name,
                environment=run_environment,
                host=run_host,
                port=run_port,
                service_target=SERVICE_TARGET,
                error="未找到 bentoml 命令，请确认 BentoML 已正确安装",
            )

            raise typer.Exit(1)

        process = started_process

        bind_address = build_bind_address(
            host=run_host,
            port=run_port,
        )
        service_url = build_http_url(
            host=run_host,
            port=run_port,
        )

        result: ServiceStartupResult = {
            "name": service_name,
            "version": app_version,
            "environment": run_environment,
            "bind": bind_address,
            "url": service_url,
            "workers": expected_workers,
            "reload": reload_enabled,
            "pid": started_process.pid,
        }

        logger.debug(
            "运行时服务子进程已启动",
            service_name=result["name"],
            version=result["version"],
            environment=result["environment"],
            bind=result["bind"],
            url=result["url"],
            workers=result["workers"],
            reload=result["reload"],
            verbose=verbose,
            service_target=SERVICE_TARGET,
            service_id=current_service_id,
            ready_dir=str(current_ready_dir),
            pid=result["pid"],
        )

        try:
            await _wait_for_workers_ready(
                ready_dir=current_ready_dir,
                service_id=current_service_id,
                process=started_process,
                expected_workers=expected_workers,
                should_stop=lambda: stop_requested,
            )

        except TimeoutError as exc:
            await _stop_process(started_process)

            logger.error(
                "运行时服务启动失败",
                service_name=result["name"],
                environment=result["environment"],
                bind=result["bind"],
                url=result["url"],
                workers=result["workers"],
                expected_workers=expected_workers,
                service_id=current_service_id,
                ready_dir=str(current_ready_dir),
                pid=result["pid"],
                error=str(exc),
            )

            raise typer.Exit(1)

        except RuntimeError as exc:
            logger.error(
                "运行时服务启动失败",
                service_name=result["name"],
                environment=result["environment"],
                bind=result["bind"],
                url=result["url"],
                workers=result["workers"],
                service_id=current_service_id,
                ready_dir=str(current_ready_dir),
                pid=result["pid"],
                error=str(exc),
            )

            raise typer.Exit(1)

        service_started = True

        logger.debug(
            "运行时服务启动完成",
            service_id=current_service_id,
            service_name=result["name"],
            version=result["version"],
            environment=result["environment"],
            bind=result["bind"],
            url=result["url"],
            workers=result["workers"],
            reload=result["reload"],
            pid=result["pid"],
        )

        logger.info(
            "运行时服务已就绪",
            workers=result["workers"],
            startup_seconds=round(perf_counter() - startup_started, 2),
        )

        if console.is_terminal:
            console.print("按 Ctrl+C 停止服务")

        return result

    def _request_stop(
            _signum: int,
            _frame: FrameType | None,
    ) -> None:
        """记录停止请求."""
        nonlocal stop_requested

        stop_requested = True

    def _record_service_stopped(
            *,
            service_process: subprocess.Popen,
            return_code: int | None,
            stop_reason: str,
    ) -> None:
        """记录预测服务主动停止事件."""
        logger.info(
            "运行时服务已停止",
            service_name=configured_service_name,
            environment=environment,
            host=resolved_host,
            port=resolved_port,
            service_id=service_id,
            pid=service_process.pid,
            return_code=return_code,
            stop_reason=stop_reason,
        )

    def _record_service_process_exited(
            *,
            service_process: subprocess.Popen,
            return_code: int,
    ) -> None:
        """记录预测服务进程自行退出事件."""
        logger.warning(
            "运行时服务进程已退出",
            service_name=configured_service_name,
            environment=environment,
            host=resolved_host,
            port=resolved_port,
            service_id=service_id,
            pid=service_process.pid,
            return_code=return_code,
        )

    async def _stop_process(
            service_process: subprocess.Popen,
    ) -> int | None:
        """停止预测服务子进程."""
        return await asyncio.to_thread(
            _stop_service_process,
            service_process,
            ready_dir=ready_dir,
            expected_workers=expected_workers,
        )

    async def runner():
        """管理预测服务生命周期."""
        nonlocal stop_requested

        previous_sigint_handler: Callable | int | None

        try:
            previous_sigint_handler = signal.getsignal(
                signal.SIGINT,
            )

            signal.signal(
                signal.SIGINT,
                _request_stop,
            )

        except ValueError:
            previous_sigint_handler = None

        try:
            await _start_service(
                service_name=configured_service_name,
                run_environment=environment,
                run_host=resolved_host,
                run_port=resolved_port,
                reload_enabled=reload,
            )

            if process is None:
                raise typer.Exit(1)

            service_process = process

            while True:
                return_code = await _wait_for_process_exit(
                    service_process,
                    lambda: stop_requested,
                )

                if return_code is None or stop_requested:
                    return_code = await _stop_process(service_process)
                    _record_service_stopped(
                        service_process=service_process,
                        return_code=return_code,
                        stop_reason="keyboard_interrupt",
                    )

                    break

                if return_code != 0:
                    logger.error(
                        "运行时服务异常退出",
                        service_name=configured_service_name,
                        environment=environment,
                        host=resolved_host,
                        port=resolved_port,
                        service_id=service_id,
                        pid=service_process.pid,
                        return_code=return_code,
                    )

                    raise typer.Exit(return_code)

                _record_service_process_exited(
                    service_process=service_process,
                    return_code=return_code,
                )

                break

        except (
                KeyboardInterrupt,
                asyncio.CancelledError,
        ):
            stop_requested = True

            if process is not None:
                return_code = await _stop_process(
                    process,
                )

                stop_reason = (
                    "keyboard_interrupt"
                    if service_started
                    else "startup_interrupted"
                )

                _record_service_stopped(
                    service_process=process,
                    return_code=return_code,
                    stop_reason=stop_reason,
                )

        finally:
            _cleanup_ready_dir(
                ready_dir,
            )

            if previous_sigint_handler is not None:
                try:
                    signal.signal(
                        signal.SIGINT,
                        previous_sigint_handler,
                    )

                except ValueError:
                    pass

    try:
        asyncio.run(runner())

    finally:
        shutdown_logging()
