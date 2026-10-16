"""独立 Compose 的 DNS 与共享网络生命周期冒烟测试.

设置 DATAMIND_RUN_COMPOSE_SMOKE=1 与 DATAMIND_COMPOSE_SMOKE_IMAGE 后运行。
使用临时项目、网络和数据卷，不接触实际部署资源。
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import pytest
import yaml


pytestmark = pytest.mark.smoke
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_independent_compose_network_lifecycle(tmp_path: Path) -> None:
    """所有应用容器解析基础设施，应用 down 保留基础设施网络."""
    if os.getenv("DATAMIND_RUN_COMPOSE_SMOKE") != "1":
        pytest.skip("设置 DATAMIND_RUN_COMPOSE_SMOKE=1 后运行")
    image = os.getenv("DATAMIND_COMPOSE_SMOKE_IMAGE", "").strip()
    if not image:
        pytest.fail("必须提供 DATAMIND_COMPOSE_SMOKE_IMAGE")

    project = "datamind-network-smoke-" + uuid4().hex[:12]
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("COMPOSE_")
        and key not in {"REDIS_PASSWORD", "DATAMIND_ENV_FILE"}
    }
    environment["DATAMIND_IMAGE_REPOSITORY"] = "unused"
    environment["DATAMIND_IMAGE_TAG"] = "test"
    docker_root = PROJECT_ROOT / "docker"
    for source, target in (
        (".env.example", ".env.docker"),
        (".env.infrastructure.example", ".env.infrastructure"),
    ):
        shutil.copyfile(docker_root / source, tmp_path / target)

    application_services = []
    for filename in (
        "docker-compose.infrastructure.yml", "docker-compose.yml",
    ):
        document = yaml.safe_load((docker_root / filename).read_text("utf-8"))
        document["networks"]["default"]["name"] = project
        infrastructure = "infrastructure" in filename
        for name, service in document["services"].items():
            # 测试使用独立项目卷，不发布端口，避免影响本机部署。
            service.pop("ports", None)
            if not infrastructure:
                application_services.append(name)
                service["image"] = image
                # 仅验证网络，避免迁移、初始化和任务消费的业务副作用。
                service["command"] = [
                    "python", "-c", "import time; time.sleep(600)",
                ]
                service["healthcheck"] = {"disable": True}
                service["restart"] = "no"
                service.pop("profiles", None)
        (tmp_path / filename).write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8",
        )

    def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["docker", *arguments], cwd=tmp_path, env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180,
        )
        if check:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    def compose(infrastructure: bool, *arguments: str, check: bool = True):
        filename = (
            "docker-compose.infrastructure.yml" if infrastructure
            else "docker-compose.yml"
        )
        return docker(
            "compose", "--project-name", project,
            "--env-file", str(tmp_path / ".env.infrastructure"),
            "-f", filename, *arguments, check=check,
        )

    probe = (
        "import socket; "
        "[(socket.getaddrinfo(host, port), "
        "socket.create_connection((host, port), timeout=5).close()) "
        "for host, port in "
        "[('postgres', 5432), ('redis', 6379), ('minio', 9000)]]; "
        "print('DNS and TCP passed')"
    )
    try:
        compose(True, "up", "-d", "--wait", "--wait-timeout", "90",
                "--pull", "never")
        compose(False, "up", "-d", "--pull", "never")
        for service in application_services:
            result = compose(False, "exec", "-T", service,
                             "python", "-c", probe)
            assert "DNS and TCP passed" in result.stdout

        compose(False, "down")
        network = json.loads(docker("network", "inspect", project).stdout)[0]
        assert len(network["Containers"]) == 3
        running = compose(True, "ps", "--status", "running", "--services")
        assert set(running.stdout.split()) == {"postgres", "redis", "minio"}

        compose(True, "down", "--volumes")
        assert docker("network", "inspect", project, check=False).returncode != 0
    finally:
        compose(False, "down", check=False)
        compose(True, "down", "--volumes", check=False)
