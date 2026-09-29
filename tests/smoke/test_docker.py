"""Docker 镜像冒烟测试.

构建 Docker 镜像，验证应用通过 Wheel 安装，并检查版本信息、OCI 元数据与
Console 首页。

核心功能：
  - test_docker_image_uses_wheel_and_exposes_metadata:
    验证 Docker 镜像安装 Wheel 发布产物并可启动管理控制台
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

import pytest

from build_support.docker import load_docker_metadata
from build_support.identity import release_build_identity
from datamind.cli.branding import short_commit


pytestmark = pytest.mark.smoke
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"
PYTHON_BASE_DIGEST = (
    "sha256:1aaa65a85fda306ffb8b910824d4e93bdce61e212c7e87168123ea3073b41a1a"
)
FRAMEWORK_MODULES = {
    "sklearn": "sklearn",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",
    "catboost": "catboost",
}


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


@dataclass(frozen=True, slots=True)
class DockerCommandResult:
    """Docker 命令执行结果."""

    exit_code: int
    output: str
    error_output: str


def docker_command(
    arguments: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: int = 300,
) -> DockerCommandResult:
    """执行 Docker 命令并返回 UTF-8 文本结果."""
    completed = subprocess.run(
        ["docker", *arguments],
        cwd=PROJECT_ROOT,
        input=input_text,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return DockerCommandResult(
        exit_code=completed.returncode,
        output=completed.stdout,
        error_output=completed.stderr,
    )


def verify_image_framework(image: str, framework: str) -> None:
    """验证镜像中的模型框架兼容性."""
    docker_command(
        [
            "run",
            "--rm",
            "--interactive",
            image,
            "python",
            "-",
            framework,
        ],
        input_text=(
            PROJECT_ROOT / "scripts" / "verify_framework.py"
        ).read_text(encoding="utf-8"),
        timeout=300,
    )


def free_port() -> int:
    """分配当前可用的本地端口."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def wait_for_console(container: str, port: int) -> str:
    """等待 Console 首页就绪并返回响应内容."""
    deadline = time.monotonic() + 180

    while time.monotonic() < deadline:
        state = docker_command(
            ["inspect", "--format", "{{.State.Running}}", container],
            check=False,
            timeout=30,
        )
        if state.exit_code != 0 or state.output.strip() != "true":
            logs = docker_command(
                ["logs", container],
                check=False,
                timeout=30,
            )
            pytest.fail(
                f"Console 容器提前退出：\n{logs.output}\n{logs.error_output}"
            )

        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/",
                timeout=3,
            ) as response:
                if response.status == 200:
                    return response.read().decode("utf-8")
        except OSError:
            time.sleep(1)

    logs = docker_command(
        ["logs", container],
        check=False,
        timeout=30,
    )
    pytest.fail(
        f"Console 未在 180 秒内就绪：\n{logs.output}\n{logs.error_output}"
    )


def test_docker_image_uses_wheel_and_exposes_metadata(
        framework: str,
) -> None:
    """测试运行时镜像的安装来源、元数据与控制台可用性."""
    if os.getenv("DATAMIND_RUN_DOCKER_SMOKE") != "1":
        pytest.skip("设置 DATAMIND_RUN_DOCKER_SMOKE=1 后运行 Docker Smoke")

    suffix = uuid4().hex[:12]
    configured_image = os.getenv("DATAMIND_SMOKE_DOCKER_IMAGE", "").strip()
    image = configured_image or f"datamind:smoke-{framework}-{suffix}"
    container = f"datamind-smoke-{suffix}"
    metadata = load_docker_metadata()
    build_environment = os.environ.copy()
    build_commit, build_date = expected_build_identity()

    try:
        if not configured_image:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.build_docker",
                    "--image",
                    image,
                    "--framework",
                    framework,
                    "--build-commit",
                    build_commit,
                    "--build-date",
                    build_date,
                ],
                cwd=PROJECT_ROOT,
                env=build_environment,
                check=True,
                timeout=1800,
            )

        version_output = docker_command(
            ["run", "--rm", image, "datamind", "--version"],
            timeout=120,
        ).output.strip()
        expected_output = (
            f"datamind version {metadata.version} "
            f"(commit {short_commit(build_commit)}, built {build_date})"
        )
        assert version_output == expected_output

        module_path = docker_command(
            [
                "run",
                "--rm",
                image,
                "python",
                "-c",
                "import datamind; print(datamind.__file__)",
            ],
            timeout=120,
        ).output.strip()
        normalized_path = module_path.replace("\\", "/").lower()
        assert "site-packages/datamind/" in normalized_path
        assert "/app/datamind/" not in normalized_path

        labels_result = docker_command(
            [
                "image",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                image,
            ],
            timeout=120,
        )
        labels = json.loads(labels_result.output)
        expected_labels = {
            "org.opencontainers.image.authors": metadata.authors,
            "org.opencontainers.image.base.name": (
                "docker.io/library/python:3.12-slim-bookworm"
            ),
            "org.opencontainers.image.base.digest": PYTHON_BASE_DIGEST,
            "org.opencontainers.image.created": build_date,
            "org.opencontainers.image.description": metadata.description,
            "org.opencontainers.image.documentation": metadata.documentation,
            "org.opencontainers.image.licenses": metadata.licenses,
            "org.opencontainers.image.revision": build_commit,
            "org.opencontainers.image.source": metadata.source,
            "org.opencontainers.image.title": metadata.title,
            "org.opencontainers.image.url": metadata.url,
            "org.opencontainers.image.vendor": metadata.vendor,
            "org.opencontainers.image.version": metadata.version,
            "io.github.zhongsheng-chen.datamind.framework": framework,
        }

        for key, expected in expected_labels.items():
            assert labels[key] == expected

        assert labels["org.opencontainers.image.authors"] == (
            "Zhongsheng Chen <zhongsheng.chen@bankgy.com.cn>"
        )
        assert labels["org.opencontainers.image.vendor"] == (
            "BANK OF GUIYANG CO., LTD."
        )
        assert labels["org.opencontainers.image.licenses"] == "Apache-2.0"

        expected_frameworks = (
            set(FRAMEWORK_MODULES)
            if framework == "full"
            else {framework}
        )
        framework_check = "\n".join([
            "import importlib.util",
            "from datamind.core.inference.adapters.factory import "
            "ModelAdapterFactory",
            "import datamind.runtime",
            f"expected = {sorted(expected_frameworks)!r}",
            f"modules = {FRAMEWORK_MODULES!r}",
            "for framework, module in modules.items():",
            "    available = importlib.util.find_spec(module) is not None",
            "    assert available == (framework in expected), "
            "(framework, available, expected)",
        ])
        docker_command(
            ["run", "--rm", image, "python", "-c", framework_check],
            timeout=120,
        )

        verify_image_framework(image, framework)

        if framework == "full":
            database_url = os.getenv(
                "DATAMIND_SMOKE_DATABASE_URL",
                "",
            ).strip()
            if not database_url:
                raise ValueError(
                    "DATAMIND_SMOKE_DATABASE_URL "
                    "必须提供测试数据库连接地址"
                )

            port = free_port()
            docker_command(
                [
                    "run",
                    "--detach",
                    "--name",
                    container,
                    "--add-host",
                    "host.docker.internal:host-gateway",
                    "--publish",
                    f"127.0.0.1:{port}:8701",
                    "--env",
                    "DATAMIND_AUTH_ENABLED=false",
                    "--env",
                    f"DATAMIND_DATABASE_URL={database_url}",
                    "--env",
                    "DATAMIND_LOG_ENABLE_FILE=false",
                    "--env",
                    "DATAMIND_SERVICE_ENVIRONMENT=development",
                    "--env",
                    "DATAMIND_STORAGE_TYPE=local",
                    image,
                    "datamind",
                    "console",
                    "run",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8701",
                    "--startup-timeout",
                    "120",
                ],
                timeout=120,
            )
            response_body = wait_for_console(container, port)
            assert "Datamind 管理控制台" in response_body
            assert "assets/index-" in response_body
    finally:
        docker_command(
            ["container", "rm", "--force", container],
            check=False,
            timeout=60,
        )
        if not configured_image:
            docker_command(
                ["image", "rm", "--force", image],
                check=False,
                timeout=120,
            )
