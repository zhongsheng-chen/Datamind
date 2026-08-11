# tests/storage/test_admin.py

"""存储管理 API 测试

验证结构化存储操作、按 key 操作、数据校验和严格删除行为。

核心功能：
  - test_init_creates_backend_and_exposes_storage_type:
    验证初始化后端及存储类型
  - test_save_with_model_fields_builds_key_and_writes_data:
    验证结构化保存构造存储键并写入数据
  - test_save_prefers_explicit_key:
    验证显式存储键优先
  - test_structured_operations_require_complete_key_fields:
    验证结构化操作要求完整参数
  - test_save_rejects_non_bytes_data:
    验证拒绝非字节数据
  - test_save_rejects_data_exceeding_size_limit:
    验证拒绝超过大小限制的数据
  - test_load_with_model_fields_returns_backend_data:
    验证结构化加载返回后端数据
  - test_exists_with_explicit_key_delegates_to_backend:
    验证存在判断委托给后端
  - test_delete_non_strict_does_not_check_existence:
    验证非严格删除不预查对象
  - test_delete_strict_raises_when_object_is_missing:
    验证严格删除拒绝不存在对象
  - test_delete_strict_removes_existing_object:
    验证严格删除已有对象
  - test_list_returns_relative_model_keys:
    验证列表返回模型相对键
  - test_list_rejects_invalid_model_id:
    验证列表拒绝非法模型 ID
  - test_save_by_key_validates_and_writes_data:
    验证按键保存的数据校验和写入
  - test_save_by_key_rejects_oversized_data:
    验证按键保存拒绝超限数据
  - test_structured_save_uses_configured_model_dir:
    验证结构化保存使用配置的模型目录
  - test_load_by_key_returns_backend_data:
    验证按键加载返回后端数据
  - test_delete_by_key_strict_raises_when_missing:
    验证按键严格删除拒绝不存在对象
  - test_delete_by_key_non_strict_delegates_directly:
    验证按键非严格删除直接委托
  - test_exists_by_key_returns_backend_result:
    验证按键存在判断返回后端结果
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
from datamind.storage import admin as admin_module
from datamind.storage.admin import StorageAdmin
from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import StorageNotFoundError


class RecordingBackend(BaseStorageBackend):
    """记录存储操作的测试后端"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[tuple[str, bytes]] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.exists_calls: list[str] = []
        self.list_calls: list[str] = []
        self.list_result: list[str] | None = None

    def put_object(
        self,
        key: str,
        data: bytes,
    ) -> None:
        """保存并记录对象"""
        self.put_calls.append(
            (
                key,
                data,
            )
        )
        self.objects[key] = data

    def get_object(
        self,
        key: str,
    ) -> bytes:
        """读取并记录对象"""
        self.get_calls.append(key)
        return self.objects[key]

    def delete_object(
        self,
        key: str,
    ) -> None:
        """删除并记录对象"""
        self.delete_calls.append(key)
        self.objects.pop(
            key,
            None,
        )

    def object_exists(
        self,
        key: str,
    ) -> bool:
        """检查并记录对象"""
        self.exists_calls.append(key)
        return key in self.objects

    def list_objects(
        self,
        prefix: str,
    ) -> list[str]:
        """列出并记录对象"""
        self.list_calls.append(prefix)

        if self.list_result is not None:
            return self.list_result.copy()

        return sorted(
            key
            for key in self.objects
            if key.startswith(prefix)
        )


def create_config(
    *,
    max_file_size: int = 1024,
    model_dir: str = "models",
) -> StorageConfig:
    """创建不读取外部配置源的存储配置"""
    local = LocalStorageConfig.model_construct(
        base_dir=Path("./data")
    )
    minio = MinIOStorageConfig.model_construct(
        endpoint="localhost:9000",
        bucket="datamind",
        access_key="",
        secret_key="",
        secure=False,
        region=None,
        base_prefix="datamind",
    )

    return StorageConfig.model_construct(
        type=StorageType.LOCAL,
        max_file_size=max_file_size,
        model_dir=model_dir,
        local=local,
        minio=minio,
    )


def create_admin(
    monkeypatch: pytest.MonkeyPatch,
    *,
    max_file_size: int = 1024,
    model_dir: str = "models",
) -> tuple[StorageAdmin, RecordingBackend]:
    """创建使用记录后端的存储管理对象"""
    backend = RecordingBackend()
    received_configs: list[StorageConfig] = []

    def fake_get_backend(
        storage_config: StorageConfig,
    ) -> BaseStorageBackend:
        received_configs.append(
            storage_config
        )
        return backend

    monkeypatch.setitem(
        vars(admin_module),
        "get_backend",
        fake_get_backend,
    )

    config = create_config(
        max_file_size=max_file_size,
        model_dir=model_dir,
    )
    storage_admin = StorageAdmin(config)

    assert received_configs == [
        config,
    ]

    return storage_admin, backend


def test_init_creates_backend_and_exposes_storage_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化后端并返回后端类型名称"""
    storage_admin, backend = create_admin(
        monkeypatch
    )

    assert storage_admin.config.model_dir == "models"
    assert storage_admin.backend is backend
    assert storage_admin.storage_type == "RecordingBackend"


def test_save_with_model_fields_builds_key_and_writes_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试根据模型字段构造存储键并保存"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    data = b"model data"

    key = storage_admin.save(
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_0123456789abcdef",
        filename="model.pkl",
        data=data,
    )

    assert key == (
        "models/scorecard/"
        "1.0.0/artifacts/"
        "art_0123456789abcdef/model.pkl"
    )
    assert backend.put_calls == [
        (
            key,
            data,
        ),
    ]


def test_save_prefers_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试显式 key 优先于模型字段"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    explicit_key = "custom/model.pkl"

    key = storage_admin.save(
        key=explicit_key,
        model_name="scorecard",
        version="1.0.0",
        filename="model.pkl",
        data=b"data",
    )

    assert key == explicit_key
    assert backend.put_calls == [
        (
            explicit_key,
            b"data",
        ),
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {
            "model_name": "scorecard",
        },
        {
            "model_name": "scorecard",
            "version": "1.0.0",
        },
        {
            "version": "1.0.0",
            "artifact_id": "art_0123456789abcdef",
            "filename": "model.pkl",
        },
        {
            "model_name": "scorecard",
            "version": "1.0.0",
            "filename": "model.pkl",
        },
    ],
)
def test_structured_operations_require_complete_key_fields(
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, Any],
) -> None:
    """测试结构化操作要求完整模型字段"""
    storage_admin, backend = create_admin(
        monkeypatch
    )

    with pytest.raises(
        ValueError,
        match=(
            "必须提供 key 或 "
            "\\(model_name, version, artifact_id, filename\\) 四参数"
        ),
    ):
        storage_admin.save(
            data=b"data",
            **arguments,
        )

    assert backend.put_calls == []


def test_save_rejects_non_bytes_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保存操作拒绝非 bytes 数据"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    invalid_data: Any = "model data"

    with pytest.raises(
        TypeError,
        match="存储数据必须是 bytes",
    ):
        storage_admin.save(
            key="models/model.pkl",
            data=invalid_data,
        )

    assert backend.put_calls == []


def test_save_rejects_data_exceeding_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保存操作拒绝超过大小上限的数据"""
    storage_admin, backend = create_admin(
        monkeypatch,
        max_file_size=4,
    )

    with pytest.raises(
        ValueError,
        match=(
            "文件大小超过配置上限: "
            "size=5, max_file_size=4"
        ),
    ):
        storage_admin.save(
            key="models/model.pkl",
            data=b"12345",
        )

    assert backend.put_calls == []


def test_load_with_model_fields_returns_backend_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试根据模型字段加载对象"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = (
        "models/scorecard/1.0.0/"
        "artifacts/art_0123456789abcdef/model.pkl"
    )
    backend.objects[key] = b"model data"

    data = storage_admin.load(
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_0123456789abcdef",
        filename="model.pkl",
    )

    assert data == b"model data"
    assert backend.get_calls == [
        key,
    ]


def test_exists_with_explicit_key_delegates_to_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按显式 key 检查对象"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    backend.objects[key] = b"data"

    exists = storage_admin.exists(
        key=key
    )

    assert exists is True
    assert backend.exists_calls == [
        key,
    ]


def test_delete_non_strict_does_not_check_existence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非严格删除直接调用后端删除"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_missing/1.0.0/model.pkl"

    deleted = storage_admin.delete(
        key=key,
        strict=False,
    )

    assert deleted is True
    assert backend.exists_calls == []
    assert backend.delete_calls == [
        key,
    ]


def test_delete_strict_raises_when_object_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试严格删除不存在对象时抛出标准异常"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_missing/1.0.0/model.pkl"

    with pytest.raises(
        StorageNotFoundError,
        match=f"对象不存在: {key}",
    ):
        storage_admin.delete(
            key=key,
            strict=True,
        )

    assert backend.exists_calls == [
        key,
    ]
    assert backend.delete_calls == []


def test_delete_strict_removes_existing_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试严格删除已存在对象"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    backend.objects[key] = b"data"

    deleted = storage_admin.delete(
        key=key,
        strict=True,
    )

    assert deleted is True
    assert backend.exists_calls == [
        key,
    ]
    assert backend.delete_calls == [
        key,
    ]
    assert key not in backend.objects


def test_list_returns_relative_model_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试列表结果转换为模型目录下的相对键"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    prefix = "models/scorecard/"
    backend.list_result = [
        f"{prefix}2.0.0/artifacts/art_002/model.pkl",
        "models/mdl_other/1.0.0/artifacts/art_other/model.pkl",
        f"{prefix}1.0.0/artifacts/art_001/readme.txt",
    ]

    keys = storage_admin.list(
        "scorecard"
    )

    assert backend.list_calls == [
        prefix,
    ]
    assert keys == [
        "2.0.0/artifacts/art_002/model.pkl",
        "1.0.0/artifacts/art_001/readme.txt",
    ]


def test_list_rejects_invalid_model_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试列表操作通过策略校验模型 ID"""
    storage_admin, backend = create_admin(
        monkeypatch
    )

    with pytest.raises(
        ValueError,
        match="非法的模型名称",
    ):
        storage_admin.list(
            "model/id"
        )

    assert backend.list_calls == []


def test_save_by_key_validates_and_writes_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 保存时执行数据校验"""
    storage_admin, backend = create_admin(
        monkeypatch,
        max_file_size=10,
    )
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    result_key = storage_admin.save_by_key(
        key,
        b"data",
    )

    assert result_key == key
    assert backend.put_calls == [
        (
            key,
            b"data",
        ),
    ]


def test_save_by_key_rejects_oversized_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 保存时拒绝超过上限的数据"""
    storage_admin, backend = create_admin(
        monkeypatch,
        max_file_size=3,
    )

    with pytest.raises(
        ValueError,
        match="文件大小超过配置上限",
    ):
        storage_admin.save_by_key(
            "models/model.pkl",
            b"1234",
        )

    assert backend.put_calls == []


def test_structured_save_uses_configured_model_dir(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试结构化保存使用配置的模型目录"""
    storage_admin, backend = create_admin(
        monkeypatch,
        model_dir="model_registry",
    )

    key = storage_admin.save(
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_0123456789abcdef",
        filename="model.pkl",
        data=b"model data",
    )

    assert key == (
        "model_registry/scorecard/1.0.0/"
        "artifacts/art_0123456789abcdef/model.pkl"
    )
    assert backend.put_calls == [
        (key, b"model data"),
    ]


def test_load_by_key_returns_backend_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 加载对象"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    backend.objects[key] = b"model data"

    data = storage_admin.load_by_key(key)

    assert data == b"model data"
    assert backend.get_calls == [
        key,
    ]


def test_delete_by_key_strict_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 严格删除不存在对象"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_missing/1.0.0/model.pkl"

    with pytest.raises(
        StorageNotFoundError,
        match=f"对象不存在: {key}",
    ):
        storage_admin.delete_by_key(
            key,
            strict=True,
        )

    assert backend.exists_calls == [
        key,
    ]
    assert backend.delete_calls == []


def test_delete_by_key_non_strict_delegates_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 非严格删除直接调用后端"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_missing/1.0.0/model.pkl"

    deleted = storage_admin.delete_by_key(
        key,
        strict=False,
    )

    assert deleted is True
    assert backend.exists_calls == []
    assert backend.delete_calls == [
        key,
    ]


def test_exists_by_key_returns_backend_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按 key 检查对象是否存在"""
    storage_admin, backend = create_admin(
        monkeypatch
    )
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    backend.objects[key] = b"data"

    exists = storage_admin.exists_by_key(key)

    assert exists is True
    assert backend.exists_calls == [
        key,
    ]
