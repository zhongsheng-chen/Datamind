# datamind/cli/service/run.py

"""运行服务命令

提供 Datamind Runtime Service 启动功能。

核心功能：
  - run_service: 启动模型服务

使用示例：
  python -m datamind.cli.main service run \
    --environment production \
    --host 0.0.0.0 \
    --port 3000
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import FrameType
from typing import Callable

import structlog
import typer
from rich.console import Console

from datamind._build import BUILD_COMMIT
from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.logging import setup_logging, shutdown_logging

app = typer.Typer(help="运行服务命令")
console = Console()

logger = structlog.get_logger(__name__)

SERVICE_TARGET = (
    "datamind.runtime.server.service:"
    "DatamindRuntimeService"
)

POWERED_BY = "Zhongsheng Chen"

LOGO = r"""
 ____        _                  _           _ 
|  _ \  __ _| |_ __ _ _ __ ___ (_)_ __   __| |
| | | |/ _` | __/ _` | '_ ` _ \| | '_ \ / _` |
| |_| | (_| | || (_| | | | | | | | | | | (_| |
|____/ \__,_|\__\__,_|_| |_| |_|_|_| |_|\__,_|
""".strip("\n")


def _get_app_version() -> str:
    """获取 Datamind 版本号"""
    try:
        app_version = version("datamind")

    except PackageNotFoundError:
        app_version = "unknown"

    if BUILD_COMMIT != "dev":
        app_version = f"{app_version} ({BUILD_COMMIT})"

    return app_version


def _build_startup_summary(
        result: dict,
) -> str:
    """构建启动摘要文本

    参数：
        result: 服务启动结果

    返回：
        启动摘要文本
    """
    return (
        f"{LOGO}\n\n"
        f"Datamind v{result['version']} · Powered by {POWERED_BY}\n\n"
        f"{'NAME':<16} : {result['name']}\n"
        f"{'ENVIRONMENT':<16} : {result['environment']}\n"
        f"{'HOST':<16} : {result['host']}\n"
        f"{'PORT':<16} : {result['port']}\n"
        f"{'WORKERS':<16} : {result['workers']}\n"
        f"{'RELOAD':<16} : {result['reload']}\n"
        f"{'PID':<16} : {result['pid']}"
    )


def _print_startup_summary(
        result: dict,
) -> None:
    """打印启动摘要到终端

    参数：
        result: 服务启动结果
    """
    console.print()
    console.print(LOGO, style="bold cyan")
    console.print()
    console.print(
        f"[bold]Datamind[/bold] "
        f"[cyan]v{result['version']}[/cyan] "
        f"[dim]· Powered by {POWERED_BY}[/dim]"
    )
    console.print()

    console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name']}")
    console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
    console.print(f"[cyan]{'HOST':<16}[/cyan] : {result['host']}")
    console.print(f"[cyan]{'PORT':<16}[/cyan] : {result['port']}")
    console.print(f"[cyan]{'WORKERS':<16}[/cyan] : {result['workers']}")
    console.print(f"[cyan]{'RELOAD':<16}[/cyan] : {result['reload']}")
    console.print(f"[cyan]{'PID':<16}[/cyan] : {result['pid']}")

    console.print()


def _log_startup_summary(
        result: dict,
) -> None:
    """记录服务启动事件

    参数：
        result: 服务启动结果
    """
    logger.info(
        "Datamind 服务启动",
        service_name=result["name"],
        version=result["version"],
        environment=result["environment"],
        host=result["host"],
        port=result["port"],
        workers=result["workers"],
        reload=result["reload"],
        pid=result["pid"],
    )


def _build_ready_dir(
        service_instance_id: str,
) -> Path:
    """构建 Worker 就绪标记目录

    参数：
        service_instance_id: 服务实例 ID

    返回：
        Worker 就绪标记目录
    """
    return (
            Path(tempfile.gettempdir())
            / "datamind"
            / "runtime_ready"
            / service_instance_id
    )


def _prepare_ready_dir(
        ready_dir: Path,
) -> None:
    """准备 Worker 就绪标记目录

    参数：
        ready_dir: Worker 就绪标记目录
    """
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
    """清理 Worker 就绪标记目录

    参数：
        ready_dir: Worker 就绪标记目录
    """
    if ready_dir is None:
        return

    shutil.rmtree(
        ready_dir,
        ignore_errors=True,
    )


def _read_worker_ready_files(
        *,
        ready_dir: Path,
        service_instance_id: str,
) -> set[str]:
    """读取已就绪 Worker

    参数：
        ready_dir: Worker 就绪标记目录
        service_instance_id: 服务实例 ID

    返回：
        已就绪 Worker ID 集合
    """
    worker_ids: set[str] = set()

    if not ready_dir.exists():
        return worker_ids

    for marker_path in ready_dir.glob("*.json"):
        try:
            record = json.loads(
                marker_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
                OSError,
                json.JSONDecodeError,
        ):
            continue

        if record.get("service_instance_id") != service_instance_id:
            continue

        if record.get("ready") is not True:
            continue

        worker_id = record.get(
            "worker_id"
        )

        if not worker_id:
            continue

        worker_ids.add(
            str(worker_id)
        )

    return worker_ids


async def _wait_for_workers_ready(
        *,
        ready_dir: Path,
        service_instance_id: str,
        process: subprocess.Popen,
        expected_workers: int,
        timeout_seconds: float = 60.0,
        interval_seconds: float = 0.5,
) -> set[str]:
    """等待全部 Worker 就绪

    参数：
        ready_dir: Worker 就绪标记目录
        service_instance_id: 服务实例 ID
        process: 服务子进程
        expected_workers: 预期 Worker 数量
        timeout_seconds: 等待超时时间
        interval_seconds: 探测间隔

    返回：
        已就绪 Worker ID 集合

    异常：
        RuntimeError: 服务子进程提前退出
        TimeoutError: 等待 Worker 就绪超时
    """
    loop = asyncio.get_running_loop()

    deadline = (
            loop.time()
            + timeout_seconds
    )

    last_worker_ids: tuple[str, ...] | None = None

    while True:
        return_code = process.poll()

        if return_code is not None:
            raise RuntimeError(
                "Datamind 服务子进程提前退出，"
                f"退出码: {return_code}"
            )

        ready_workers = _read_worker_ready_files(
            ready_dir=ready_dir,
            service_instance_id=service_instance_id,
        )

        current_worker_ids = tuple(
            sorted(ready_workers)
        )

        if current_worker_ids != last_worker_ids:
            logger.debug(
                "等待 Datamind 服务 Worker 就绪",
                service_instance_id=service_instance_id,
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
                "等待 Datamind 服务 Worker 启动超时: "
                f"ready_workers={len(ready_workers)}, "
                f"expected_workers={expected_workers}, "
                f"ready_dir={ready_dir}"
            )

        await asyncio.sleep(
            interval_seconds
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
):
    """启动 Datamind 模型服务"""
    settings = get_settings()

    setup_logging(
        settings.logging
    )

    service_config = settings.service
    expected_workers = int(service_config.workers)

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
    ready_dir: Path | None = None
    service_instance_id: str | None = None
    service_started = False
    stop_requested = False

    @audit(
        action="service.run",
        target_type="service",
        target_id_from="service_name",
    )
    async def _start_service(
            *,
            service_name: str,
            run_environment: str,
            run_host: str,
            run_port: int,
            reload_enabled: bool,
            actor: str,
    ) -> dict:
        """启动服务子进程并等待 Worker 就绪"""
        nonlocal process
        nonlocal ready_dir
        nonlocal service_instance_id
        nonlocal service_started

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

        app_version = _get_app_version()

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

        current_service_instance_id: str = uuid.uuid4().hex

        current_ready_dir: Path = _build_ready_dir(
            current_service_instance_id
        )

        service_instance_id = current_service_instance_id
        ready_dir = current_ready_dir

        _prepare_ready_dir(
            current_ready_dir
        )

        env = os.environ.copy()

        env["DATAMIND_SERVICE_ENVIRONMENT"] = (
            run_environment
        )

        env["DATAMIND_SERVICE_INSTANCE_ID"] = (
            current_service_instance_id
        )

        env["DATAMIND_SERVICE_READY_DIR"] = (
            str(current_ready_dir)
        )

        try:
            started_process = subprocess.Popen(
                command,
                env=env,
            )

        except FileNotFoundError:
            _cleanup_ready_dir(
                current_ready_dir
            )

            logger.error(
                "Datamind 服务启动失败",
                service_name=service_name,
                environment=run_environment,
                host=run_host,
                port=run_port,
                service_target=SERVICE_TARGET,
                error="未找到 bentoml 命令，请确认 BentoML 已正确安装",
            )

            raise typer.Exit(1)

        process = started_process

        result = {
            "name": service_name,
            "version": app_version,
            "environment": run_environment,
            "host": run_host,
            "port": run_port,
            "workers": expected_workers,
            "reload": reload_enabled,
            "pid": started_process.pid,
        }

        _print_startup_summary(result)

        _log_startup_summary(
            result=result,
        )

        logger.info(
            "Datamind 服务子进程启动成功",
            service_name=result["name"],
            version=result["version"],
            environment=result["environment"],
            host=result["host"],
            port=result["port"],
            workers=result["workers"],
            reload=result["reload"],
            operator=actor,
            service_target=SERVICE_TARGET,
            service_instance_id=current_service_instance_id,
            ready_dir=str(current_ready_dir),
            pid=result["pid"],
        )

        try:
            ready_workers = await _wait_for_workers_ready(
                ready_dir=current_ready_dir,
                service_instance_id=current_service_instance_id,
                process=started_process,
                expected_workers=expected_workers,
            )

        except TimeoutError as exc:
            logger.error(
                "Datamind 服务启动失败",
                service_name=result["name"],
                environment=result["environment"],
                host=result["host"],
                port=result["port"],
                workers=result["workers"],
                expected_workers=expected_workers,
                service_instance_id=current_service_instance_id,
                ready_dir=str(current_ready_dir),
                pid=result["pid"],
                error=str(exc),
            )

            started_process.terminate()
            await asyncio.to_thread(
                started_process.wait
            )

            raise typer.Exit(1)

        except RuntimeError as exc:
            logger.error(
                "Datamind 服务启动失败",
                service_name=result["name"],
                environment=result["environment"],
                host=result["host"],
                port=result["port"],
                workers=result["workers"],
                service_instance_id=current_service_instance_id,
                ready_dir=str(current_ready_dir),
                pid=result["pid"],
                error=str(exc),
            )

            raise typer.Exit(1)

        service_started = True

        logger.info(
            "Datamind 服务启动完成",
            service_name=result["name"],
            environment=result["environment"],
            host=result["host"],
            port=result["port"],
            workers=result["workers"],
            ready_workers=len(ready_workers),
            service_instance_id=current_service_instance_id,
            ready_dir=str(current_ready_dir),
            pid=result["pid"],
        )

        return result

    def _request_stop(
            _signum: int,
            _frame: FrameType | None,
    ) -> None:
        """记录用户停止请求并通知子进程停止"""
        nonlocal stop_requested

        stop_requested = True

        if process is not None and process.poll() is None:
            process.terminate()

    def _record_service_stopped(
            *,
            service_process: subprocess.Popen,
            return_code: int | None,
            stop_reason: str,
    ) -> None:
        """记录服务主动停止事件"""
        logger.info(
            "Datamind 服务已停止",
            service_name=configured_service_name,
            environment=resolved_environment,
            host=resolved_host,
            port=resolved_port,
            service_instance_id=service_instance_id,
            pid=service_process.pid,
            return_code=return_code,
            stop_reason=stop_reason,
        )

    def _record_service_process_exited(
            *,
            service_process: subprocess.Popen,
            return_code: int,
    ) -> None:
        """记录服务进程自行退出事件"""
        logger.warning(
            "Datamind 服务进程已退出",
            service_name=configured_service_name,
            environment=resolved_environment,
            host=resolved_host,
            port=resolved_port,
            service_instance_id=service_instance_id,
            pid=service_process.pid,
            return_code=return_code,
        )

    async def _stop_process(
            service_process: subprocess.Popen,
    ) -> int | None:
        """停止服务子进程

        参数：
            service_process: 服务子进程

        返回：
            子进程退出码
        """
        if service_process.poll() is None:
            service_process.terminate()

        return await asyncio.to_thread(
            service_process.wait
        )

    async def runner():
        nonlocal stop_requested

        previous_sigint_handler: Callable | int | None

        try:
            previous_sigint_handler = signal.getsignal(
                signal.SIGINT
            )

            signal.signal(
                signal.SIGINT,
                _request_stop
            )

        except ValueError:
            previous_sigint_handler = None

        async with cli_context(
                required_permission="runtime.manage",
        ) as context:
            setup_logging(
                settings.logging
            )

            try:
                await _start_service(
                    service_name=configured_service_name,
                    run_environment=resolved_environment,
                    run_host=resolved_host,
                    run_port=resolved_port,
                    reload_enabled=reload,
                    actor=context.user,
                )

                if process is None:
                    raise typer.Exit(1)

                service_process = process

                while True:
                    return_code = await asyncio.to_thread(
                        service_process.wait
                    )

                    if stop_requested:
                        _record_service_stopped(
                            service_process=service_process,
                            return_code=return_code,
                            stop_reason="keyboard_interrupt",
                        )

                        break

                    if return_code != 0:
                        logger.error(
                            "Datamind 服务异常退出",
                            service_name=configured_service_name,
                            environment=resolved_environment,
                            host=resolved_host,
                            port=resolved_port,
                            service_instance_id=service_instance_id,
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
                        process
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
                    ready_dir
                )

                if previous_sigint_handler is not None:
                    try:
                        signal.signal(
                            signal.SIGINT,
                            previous_sigint_handler
                        )

                    except ValueError:
                        pass

    try:
        asyncio.run(runner())

    finally:
        shutdown_logging()
