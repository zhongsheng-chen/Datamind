# tests/storage/test_factory.py

"""存储后端工厂测试

验证工厂根据存储类型创建后端并正确传递配置参数。

核心功能：
  - test_get_backend_creates_local_backend:
    验证创建本地存储后端
  - test_get_backend_creates_minio_backend:
    验证创建 MinIO 后端并传递配置
  - test_get_backend_rejects_unknown_storage_type:
    验证拒绝未知存储类型
"""

from pathlib import Path
from typing import Any

import pytest

from datamind.config.storage import (
    LocalStorageConfig,
    MinIOStorageConfig,
    StorageConfig,
)
from datamind.constants import StorageType
from datamind.storage import factory
from datamind.storage.base import BaseStorageBackend


class DummyBackend(BaseStorageBackend):
    """用于验证工厂返回值的测试存储后端"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(
        self,
        key: str,
        data: bytes,
    ) -> None:
        """保存测试对象"""
        self.objects[key] = data

    def get_object(
        self,
        key: str,
    ) -> bytes:
        """读取测试对象"""
        return self.objects[key]

    def delete_object(
        self,
        key: str,
    ) -> None:
        """删除测试对象"""
        self.objects.pop(
            key,
            None,
        )

    def object_exists(
        self,
        key: str,
    ) -> bool:
        """检查测试对象是否存在"""
        return key in self.objects

    def list_objects(
        self,
        prefix: str,
    ) -> list[str]:
        """列出匹配前缀的测试对象"""
        return sorted(
            key
            for key in self.objects
            if key.startswith(prefix)
        )


def create_config(
    *,
    storage_type: StorageType | str,
) -> StorageConfig:
    """创建不读取外部配置源的存储配置"""
    local = LocalStorageConfig.model_construct(
        base_dir=Path("/srv/datamind/data")
    )
    minio = MinIOStorageConfig.model_construct(
        endpoint="minio.internal:9000",
        bucket="datamind-models",
        access_key="access-key",
        secret_key="secret-key",
        secure=True,
        region="cn-north-1",
        base_prefix="artifacts",
    )

    return StorageConfig.model_construct(
        type=storage_type,
        max_file_size=200 * 1024 * 1024,
        model_dir="models",
        local=local,
        minio=minio,
    )


def test_get_backend_creates_local_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地类型创建本地存储后端"""
    expected_backend = DummyBackend()
    received: dict[str, Any] = {}

    def fake_local_backend(
        *,
        base_dir: Path,
    ) -> DummyBackend:
        received["base_dir"] = base_dir
        return expected_backend

    def fail_minio_backend(
        **_options: Any,
    ) -> DummyBackend:
        raise AssertionError(
            "本地存储配置不应创建 MinIO 后端"
        )

    monkeypatch.setitem(
        vars(factory),
        "LocalStorageBackend",
        fake_local_backend,
    )
    monkeypatch.setitem(
        vars(factory),
        "MinIOStorageBackend",
        fail_minio_backend,
    )

    config = create_config(
        storage_type=StorageType.LOCAL
    )

    backend = factory.get_backend(config)

    assert backend is expected_backend
    assert received == {
        "base_dir": Path("/srv/datamind/data"),
    }


def test_get_backend_creates_minio_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 MinIO 类型创建 MinIO 存储后端"""
    expected_backend = DummyBackend()
    received: dict[str, Any] = {}

    def fail_local_backend(
        *,
        base_dir: Path,
    ) -> DummyBackend:
        raise AssertionError(
            "MinIO 配置不应创建本地后端: "
            f"{base_dir}"
        )

    def fake_minio_backend(
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        base_prefix: str,
        region: str | None,
    ) -> DummyBackend:
        received.update(
            {
                "endpoint": endpoint,
                "access_key": access_key,
                "secret_key": secret_key,
                "bucket": bucket,
                "secure": secure,
                "base_prefix": base_prefix,
                "region": region,
            }
        )
        return expected_backend

    monkeypatch.setitem(
        vars(factory),
        "LocalStorageBackend",
        fail_local_backend,
    )
    monkeypatch.setitem(
        vars(factory),
        "MinIOStorageBackend",
        fake_minio_backend,
    )

    config = create_config(
        storage_type=StorageType.MINIO
    )

    backend = factory.get_backend(config)

    assert backend is expected_backend
    assert received == {
        "endpoint": "minio.internal:9000",
        "access_key": "access-key",
        "secret_key": "secret-key",
        "bucket": "datamind-models",
        "secure": True,
        "base_prefix": "artifacts",
        "region": "cn-north-1",
    }


def test_get_backend_rejects_unknown_storage_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝未知存储类型"""

    def fail_local_backend(
        **_options: Any,
    ) -> DummyBackend:
        raise AssertionError(
            "未知类型不应创建本地后端"
        )

    def fail_minio_backend(
        **_options: Any,
    ) -> DummyBackend:
        raise AssertionError(
            "未知类型不应创建 MinIO 后端"
        )

    monkeypatch.setitem(
        vars(factory),
        "LocalStorageBackend",
        fail_local_backend,
    )
    monkeypatch.setitem(
        vars(factory),
        "MinIOStorageBackend",
        fail_minio_backend,
    )

    config = create_config(
        storage_type="unknown"
    )

    with pytest.raises(
        ValueError,
        match="不支持的存储类型: unknown",
    ):
        factory.get_backend(config)
