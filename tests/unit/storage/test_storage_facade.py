"""存储门面测试.

验证 Storage 的核心参数委托以及 get_storage() 的单例缓存行为。

核心功能：
  - test_save_delegates_structured_arguments:
    验证保存操作委托结构化参数
  - test_load_by_key_delegates_storage_key:
    验证按键加载委托存储键
  - test_delete_by_key_delegates_strict_mode:
    验证按键删除委托严格模式
  - test_get_storage_returns_cached_singleton:
    验证全局存储返回缓存单例
  - test_cache_clear_creates_new_storage_instance:
    验证清除缓存后创建新实例
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import create_autospec

import pytest

import datamind.storage as storage_module
from datamind.config.storage import StorageConfig
from datamind.storage import Storage, get_storage
from datamind.storage.admin import StorageAdmin

@pytest.fixture(autouse=True)
def clear_storage_cache() -> Iterator[None]:
    """测试前后清理全局存储缓存."""
    get_storage.cache_clear()

    yield

    get_storage.cache_clear()


def create_storage_admin_mock() -> Any:
    """创建符合 StorageAdmin 接口的测试替身."""
    return create_autospec(
        StorageAdmin,
        instance=True,
    )


def test_save_delegates_structured_arguments() -> None:
    """测试保存方法正确委托结构化参数."""
    storage_admin = create_storage_admin_mock()
    storage_admin.save.return_value = (
        "models/mdl_001/1.0.0/artifacts/art_001/model.pkl"
    )
    storage = Storage(
        storage_admin
    )

    storage_key = storage.save(
        "scorecard",
        "1.0.0",
        "art_001",
        "model.pkl",
        b"model data",
    )

    assert storage_key == (
        "models/mdl_001/1.0.0/artifacts/art_001/model.pkl"
    )
    storage_admin.save.assert_called_once_with(
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_001",
        filename="model.pkl",
        data=b"model data",
    )


def test_load_by_key_delegates_storage_key() -> None:
    """测试按存储键加载方法正确委托参数."""
    storage_admin = create_storage_admin_mock()
    storage_admin.load_by_key.return_value = (
        b"model data"
    )
    storage = Storage(
        storage_admin
    )
    key = "models/mdl_001/1.0.0/artifacts/art_001/model.pkl"

    data = storage.load_by_key(
        key
    )

    assert data == b"model data"
    storage_admin.load_by_key.assert_called_once_with(
        key
    )


def test_delete_by_key_delegates_strict_mode() -> None:
    """测试按存储键删除方法正确传递严格模式."""
    storage_admin = create_storage_admin_mock()
    storage_admin.delete_by_key.return_value = True
    storage = Storage(
        storage_admin
    )
    key = "models/mdl_001/1.0.0/artifacts/art_001/model.pkl"

    deleted = storage.delete_by_key(
        key,
        strict=True,
    )

    assert deleted is True
    storage_admin.delete_by_key.assert_called_once_with(
        key,
        strict=True,
    )


def test_get_storage_returns_cached_singleton(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试多次调用返回同一个存储实例."""
    storage_config = StorageConfig.model_construct()
    created_configs: list[StorageConfig] = []
    config_calls = 0

    def fake_storage_config() -> StorageConfig:
        nonlocal config_calls
        config_calls += 1
        return storage_config

    def fake_storage_admin(
            config: StorageConfig,
    ) -> Any:
        created_configs.append(
            config
        )
        return create_storage_admin_mock()

    monkeypatch.setitem(
        vars(storage_module),
        "get_storage_config",
        fake_storage_config,
    )
    monkeypatch.setitem(
        vars(storage_module),
        "StorageAdmin",
        fake_storage_admin,
    )

    first_storage = get_storage()
    second_storage = get_storage()

    assert first_storage is second_storage
    assert config_calls == 1
    assert created_configs == [
        storage_config,
    ]


def test_cache_clear_creates_new_storage_instance(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试清理缓存后重新创建存储实例."""
    storage_config = StorageConfig.model_construct()
    created_configs: list[StorageConfig] = []

    def fake_storage_admin(
            config: StorageConfig,
    ) -> Any:
        created_configs.append(
            config
        )
        return create_storage_admin_mock()

    monkeypatch.setitem(
        vars(storage_module),
        "get_storage_config",
        lambda: storage_config,
    )
    monkeypatch.setitem(
        vars(storage_module),
        "StorageAdmin",
        fake_storage_admin,
    )

    first_storage = get_storage()

    get_storage.cache_clear()

    second_storage = get_storage()

    assert first_storage is not second_storage
    assert created_configs == [
        storage_config,
        storage_config,
    ]
