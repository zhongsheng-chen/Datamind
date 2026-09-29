"""Wheel 发布产物冒烟测试.

构建 Wheel 并安装至隔离虚拟环境，验证 Python 导入、版本信息、CLI 入口与
Console 首页。

核心功能：
  - test_wheel_installs_and_serves_console:
    验证 Wheel 可独立安装并启动管理控制台
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from build_support.identity import release_build_identity
from datamind.cli.branding import short_commit


pytestmark = pytest.mark.smoke
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"


@dataclass(frozen=True, slots=True)
class WheelCommandResult:
    """Wheel 命令执行结果."""

    exit_code: int
    output: str
    error_output: str


def wheel_command(
        arguments: list[str],
        *,
        cwd: Path,
        environment: dict[str, str] | None = None,
        check: bool = True,
        timeout: int = 300,
) -> WheelCommandResult:
    """执行命令并返回 UTF-8 文本结果."""
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return WheelCommandResult(
        exit_code=completed.returncode,
        output=completed.stdout,
        error_output=completed.stderr,
    )


def pip_index_arguments() -> list[str]:
    """读取可选的 pip 包索引参数."""
    configured = os.getenv("PIP_INDEX_URL", "").strip()
    if not configured:
        return []

    if configured.startswith("https://"):
        return ["--index-url", configured.rstrip("/")]

    raise ValueError("PIP_INDEX_URL 必须是 HTTPS 包索引地址")


def expected_build_identity() -> tuple[str, str]:
    """读取 Smoke 期望的构建身份，默认使用固定测试值."""
    commit = os.getenv("DATAMIND_SMOKE_BUILD_COMMIT")
    build_date = os.getenv("DATAMIND_SMOKE_BUILD_DATE")

    if commit is None and build_date is None:
        return BUILD_COMMIT, BUILD_DATE
    if commit is None or build_date is None:
        raise ValueError(
            "DATAMIND_SMOKE_BUILD_COMMIT 与 DATAMIND_SMOKE_BUILD_DATE "
            "必须同时设置"
        )

    identity = release_build_identity(commit, build_date)
    return identity.commit, identity.build_date


def prepare_console_environment(tmp_path: Path) -> dict[str, str]:
    """创建隔离的 Console 运行环境."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DATAMIND_")
    }
    environment["BENTOML_HOME"] = str(tmp_path / "bentoml")
    configured_file = os.getenv("DATAMIND_SMOKE_ENV_FILE", "").strip()

    if configured_file:
        source = Path(configured_file).expanduser().resolve()
        if not source.is_file():
            raise ValueError(
                "DATAMIND_SMOKE_ENV_FILE 必须指向已存在的文件"
            )

        shutil.copyfile(source, tmp_path / ".env")
        return environment

    database_url = os.getenv("DATAMIND_SMOKE_DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError(
            "DATAMIND_SMOKE_DATABASE_URL "
            "必须提供测试数据库连接地址"
        )

    environment.update(
        {
            "DATAMIND_AUTH_ENABLED": "false",
            "DATAMIND_DATABASE_URL": database_url,
            "DATAMIND_LOG_DIR": str(tmp_path / "logs"),
            "DATAMIND_LOG_ENABLE_FILE": "false",
            "DATAMIND_SERVICE_ENVIRONMENT": "development",
            "DATAMIND_STORAGE_TYPE": "local",
            "DATAMIND_STORAGE_LOCAL_BASE_DIR": str(tmp_path / "storage"),
        }
    )
    return environment


def executable(virtual_environment: Path, name: str) -> Path:
    """定位虚拟环境中的跨平台可执行文件."""
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return virtual_environment / directory / f"{name}{suffix}"


def free_port() -> int:
    """分配当前可用的本地端口."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    """终止 Console 进程及其子进程."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                check=False,
                capture_output=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            process.kill()
    else:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def wait_for_console(
        process: subprocess.Popen[bytes],
        port: int,
        log_path: Path,
) -> str:
    """等待 Console 首页就绪并返回响应内容."""
    deadline = time.monotonic() + 120

    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            details = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )[-4000:]
            pytest.fail(
                "Console 在就绪前退出，退出码为 "
                f"{exit_code}：\n{details}"
            )

        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/",
                    timeout=2,
            ) as response:
                if response.status == 200:
                    return response.read().decode("utf-8")
        except OSError:
            time.sleep(0.25)

    pytest.fail("Console 未在 120 秒内就绪")


def test_wheel_installs_and_serves_console(
        tmp_path: Path,
) -> None:
    """测试 Wheel 可在隔离环境中安装并启动管理控制台."""
    if os.getenv("DATAMIND_RUN_WHEEL_SMOKE") != "1":
        pytest.skip("设置 DATAMIND_RUN_WHEEL_SMOKE=1 后运行 Wheel Smoke")

    index_arguments = pip_index_arguments()
    build_commit, build_date = expected_build_identity()
    configured_wheel = os.getenv("DATAMIND_SMOKE_WHEEL", "").strip()

    if configured_wheel:
        wheel = Path(configured_wheel).expanduser().resolve()
        if not wheel.is_file():
            raise ValueError("DATAMIND_SMOKE_WHEEL 必须指向已存在的 Wheel")
    else:
        wheel_directory = tmp_path / "wheel"
        wheel_directory.mkdir()
        build_environment = os.environ.copy()
        build_environment.update(
            {
                "DATAMIND_BUILD_COMMIT": build_commit,
                "DATAMIND_BUILD_DATE": build_date,
            }
        )
        wheel_command(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                *index_arguments,
                "--wheel-dir",
                str(wheel_directory),
            ],
            cwd=PROJECT_ROOT,
            environment=build_environment,
            timeout=300,
        )
        wheels = list(wheel_directory.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Wheel 构建目录必须且只能包含一个 Wheel")
        wheel = wheels[0]

    virtual_environment = tmp_path / "venv"
    wheel_command(
        [
            sys.executable,
            "-m",
            "venv",
            str(virtual_environment),
        ],
        cwd=tmp_path,
        timeout=120,
    )
    pip = executable(virtual_environment, "pip")
    python = executable(virtual_environment, "python")
    datamind = executable(virtual_environment, "datamind")
    wheel_command(
        [
            str(pip),
            "install",
            "--disable-pip-version-check",
            *index_arguments,
            str(wheel),
        ],
        cwd=tmp_path,
        timeout=600,
    )
    wheel_command(
        [str(pip), "check"],
        cwd=tmp_path,
        timeout=120,
    )
    import_result = wheel_command(
        [
            str(python),
            "-c",
            "import datamind; print(datamind.__file__)",
        ],
        cwd=tmp_path,
        check=False,
        timeout=90,
    )
    assert import_result.exit_code == 0, import_result.error_output
    assert "datamind" in import_result.output
    help_result = wheel_command(
        [str(datamind), "--help"],
        cwd=tmp_path,
        check=False,
        timeout=90,
    )
    assert help_result.exit_code == 0, help_result.error_output
    assert "console" in help_result.output

    version_result = wheel_command(
        [str(datamind), "--version"],
        cwd=tmp_path,
        check=False,
        timeout=90,
    )
    assert version_result.exit_code == 0, version_result.error_output
    expected_version = (
        f"commit {short_commit(build_commit)}, "
        f"built {build_date}"
    )
    assert expected_version in version_result.output

    port = free_port()
    console_environment = prepare_console_environment(tmp_path)
    console_log_path = tmp_path / "console.log"

    with console_log_path.open("wb") as console_log:
        process = subprocess.Popen(
            [
                str(datamind),
                "console",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--startup-timeout",
                "120",
            ],
            cwd=tmp_path,
            env=console_environment,
            stdout=console_log,
            stderr=subprocess.STDOUT,
        )

        try:
            response_body = wait_for_console(
                process,
                port,
                console_log_path,
            )
            assert "Datamind 管理控制台" in response_body
            assert "assets/index-" in response_body
        finally:
            stop_process_tree(process)
