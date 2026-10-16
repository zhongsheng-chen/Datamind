"""Docker Compose 网络归属与连接配置测试."""

from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
import pytest
import yaml

from datamind.config.database import DatabaseConfig
from datamind.config.queue import TaskQueueConfig
from datamind.config.storage import MinIOStorageConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_compose_network_has_one_owner() -> None:
    """基础设施管理共享网络，所有应用服务通过外部网络加入."""
    documents = [
        yaml.safe_load((PROJECT_ROOT / "docker" / name).read_text("utf-8"))
        for name in ("docker-compose.infrastructure.yml", "docker-compose.yml")
    ]
    infrastructure, application = documents

    assert infrastructure["name"] == application["name"] == "datamind"
    assert infrastructure["networks"]["default"]["name"] == "datamind"
    assert not infrastructure["networks"]["default"].get("external", False)
    assert application["networks"]["default"] == {
        "name": "datamind",
        "external": True,
    }
    assert set(infrastructure["services"]) == {"postgres", "redis", "minio"}
    assert set(application["services"]) == {
        "runtime", "console", "batch-worker-a", "batch-worker-b",
        "shadow-worker", "migrate", "init",
    }
    for document in documents:
        for service in document["services"].values():
            assert "container_name" not in service
            assert "network_mode" not in service
            assert set(service.get("networks", ["default"])) == {"default"}

    assert infrastructure["services"]["postgres"]["ports"] == [
        "127.0.0.1:5432:5432",
    ]
    assert infrastructure["services"]["redis"]["ports"] == [
        "127.0.0.1:6379:6379",
    ]
    assert infrastructure["services"]["minio"]["ports"] == [
        "127.0.0.1:9000:9000", "127.0.0.1:9001:9001",
    ]


def test_docker_environment_uses_actual_configuration_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """通过实际配置模型验证 Docker 模板中的基础设施连接变量."""
    content = (PROJECT_ROOT / "docker" / ".env.example").read_text("utf-8")
    values = dotenv_values(stream=StringIO(content))
    monkeypatch.chdir(tmp_path)
    for name, value in values.items():
        assert value is not None
        monkeypatch.setenv(name, value)

    database = DatabaseConfig(_env_file=None)
    queue = TaskQueueConfig(_env_file=None)
    storage = MinIOStorageConfig(_env_file=None)

    assert urlsplit(database.url).hostname == "postgres"
    assert urlsplit(database.url).port == 5432
    assert urlsplit(queue.broker_url).hostname == "redis"
    assert urlsplit(queue.broker_url).port == 6379
    assert storage.endpoint == "minio:9000"
    assert storage.bucket == values["DATAMIND_STORAGE_MINIO_BUCKET"]
    assert storage.access_key == values["DATAMIND_STORAGE_MINIO_ACCESS_KEY"]
    assert storage.secret_key == values["DATAMIND_STORAGE_MINIO_SECRET_KEY"]
