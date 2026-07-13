# tests/storage/test_resolver.py

"""存储路径解析器测试

验证本地路径、MinIO URI、存储键校验和存储类型分派。

核心功能：
  - test_init_uses_current_settings:
    验证初始化读取当前配置
  - test_resolve_local_returns_absolute_path:
    验证本地键解析为绝对路径
  - test_resolve_local_normalizes_windows_separators:
    验证本地路径标准化 Windows 分隔符
  - test_resolve_local_expands_user_directory:
    验证展开用户目录
  - test_resolve_minio_builds_s3_uri_with_base_prefix:
    验证构造含基础前缀的 S3 URI
  - test_resolve_minio_normalizes_key_and_prefix_separators:
    验证 MinIO 键和前缀分隔符规范化
  - test_resolve_minio_without_base_prefix:
    验证无基础前缀的 S3 URI
  - test_resolve_minio_rejects_invalid_bucket:
    验证拒绝非法存储桶
  - test_resolve_minio_rejects_invalid_base_prefix:
    验证拒绝非法基础前缀
  - test_resolve_rejects_invalid_string_keys:
    验证拒绝非法字符串键
  - test_resolve_rejects_non_string_keys:
    验证拒绝非字符串键
  - test_resolve_rejects_unknown_storage_type:
    验证拒绝未知存储类型
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from datamind.constants import StorageType
from datamind.storage import resolver as resolver_module
from datamind.storage.errors import StorageKeyError
from datamind.storage.resolver import StorageResolver


@dataclass(frozen=True)
class LocalConfigStub:
    """本地存储配置测试桩"""

    base_dir: Path


@dataclass(frozen=True)
class MinIOConfigStub:
    """MinIO 存储配置测试桩"""

    bucket: str
    base_prefix: str


@dataclass(frozen=True)
class StorageConfigStub:
    """存储配置测试桩"""

    type: StorageType | str
    local: LocalConfigStub
    minio: MinIOConfigStub


@dataclass(frozen=True)
class SettingsStub:
    """全局配置测试桩"""

    storage: StorageConfigStub


def create_resolver(
    monkeypatch: pytest.MonkeyPatch,
    *,
    storage_type: StorageType | str,
    base_dir: Path,
    bucket: str = "datamind",
    base_prefix: str = "artifacts",
) -> StorageResolver:
    """创建使用指定存储配置的路径解析器"""
    settings = SettingsStub(
        storage=StorageConfigStub(
            type=storage_type,
            local=LocalConfigStub(
                base_dir=base_dir
            ),
            minio=MinIOConfigStub(
                bucket=bucket,
                base_prefix=base_prefix,
            ),
        )
    )

    monkeypatch.setitem(
        vars(resolver_module),
        "get_settings",
        lambda: settings,
    )

    return StorageResolver()


def test_init_uses_current_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试初始化时读取当前全局配置"""
    settings = SettingsStub(
        storage=StorageConfigStub(
            type=StorageType.LOCAL,
            local=LocalConfigStub(
                base_dir=tmp_path
            ),
            minio=MinIOConfigStub(
                bucket="datamind",
                base_prefix="artifacts",
            ),
        )
    )

    monkeypatch.setitem(
        vars(resolver_module),
        "get_settings",
        lambda: settings,
    )

    storage_resolver = StorageResolver()

    assert storage_resolver.settings is settings


def test_resolve_local_returns_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试本地存储键解析为绝对路径"""
    base_dir = tmp_path / "data"
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.LOCAL,
        base_dir=base_dir,
    )

    resolved = storage_resolver.resolve(
        "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    )

    expected = (
        base_dir
        / "models"
        / "mdl_0123456789abcdef"
        / "1.0.0"
        / "model.pkl"
    ).resolve()

    assert resolved == str(expected)
    assert Path(resolved).is_absolute()


def test_resolve_local_normalizes_windows_separators(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试本地解析时标准化 Windows 路径分隔符"""
    base_dir = tmp_path / "data"
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.LOCAL,
        base_dir=base_dir,
    )

    resolved = storage_resolver.resolve(
        r"models\mdl_0123456789abcdef\1.0.0\model.pkl"
    )

    expected = (
        base_dir
        / "models"
        / "mdl_0123456789abcdef"
        / "1.0.0"
        / "model.pkl"
    ).resolve()

    assert resolved == str(expected)


def test_resolve_local_expands_user_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试本地基础目录执行 expanduser 和 resolve"""
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    monkeypatch.setenv(
        "HOME",
        str(fake_home),
    )
    monkeypatch.setenv(
        "USERPROFILE",
        str(fake_home),
    )

    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.LOCAL,
        base_dir=Path("~/datamind-data"),
    )

    resolved = storage_resolver.resolve(
        "models/model.pkl"
    )

    expected = (
        fake_home
        / "datamind-data"
        / "models"
        / "model.pkl"
    ).resolve()

    assert resolved == str(expected)


def test_resolve_minio_builds_s3_uri_with_base_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试 MinIO 路径包含存储桶和基础前缀"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.MINIO,
        base_dir=tmp_path,
        bucket="datamind-models",
        base_prefix="artifacts",
    )

    resolved = storage_resolver.resolve(
        "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    )

    assert resolved == (
        "s3://datamind-models/"
        "artifacts/models/mdl_0123456789abcdef/"
        "1.0.0/model.pkl"
    )


def test_resolve_minio_normalizes_key_and_prefix_separators(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试 MinIO 路径标准化键和前缀分隔符"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.MINIO,
        base_dir=tmp_path,
        bucket=" datamind ",
        base_prefix=r"\artifacts\models/",
    )

    resolved = storage_resolver.resolve(
        r"registry\mdl_0123456789abcdef\model.pkl"
    )

    assert resolved == (
        "s3://datamind/"
        "artifacts/models/"
        "registry/mdl_0123456789abcdef/model.pkl"
    )


@pytest.mark.parametrize(
    "base_prefix",
    [
        "",
        "   ",
        "/",
        r"\\",
    ],
)
def test_resolve_minio_without_base_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    base_prefix: str,
) -> None:
    """测试基础前缀为空时直接拼接逻辑键"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.MINIO,
        base_dir=tmp_path,
        bucket="datamind",
        base_prefix=base_prefix,
    )

    resolved = storage_resolver.resolve(
        "models/model.pkl"
    )

    assert resolved == (
        "s3://datamind/models/model.pkl"
    )


@pytest.mark.parametrize(
    "bucket",
    [
        "",
        "   ",
        "data/mind",
        r"data\mind",
    ],
)
def test_resolve_minio_rejects_invalid_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bucket: str,
) -> None:
    """测试拒绝空桶名和包含路径分隔符的桶名"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.MINIO,
        base_dir=tmp_path,
        bucket=bucket,
    )

    with pytest.raises(
        StorageKeyError,
        match="非法的 MinIO 存储桶名称",
    ):
        storage_resolver.resolve(
            "models/model.pkl"
        )


@pytest.mark.parametrize(
    "base_prefix",
    [
        "artifacts//models",
        "artifacts/./models",
        "artifacts/../models",
        "artifacts\x00models",
    ],
)
def test_resolve_minio_rejects_invalid_base_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    base_prefix: str,
) -> None:
    """测试 MinIO 基础前缀复用存储键校验规则"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.MINIO,
        base_dir=tmp_path,
        base_prefix=base_prefix,
    )

    with pytest.raises(StorageKeyError):
        storage_resolver.resolve(
            "models/model.pkl"
        )


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/models/model.pkl",
        "models//model.pkl",
        "models/./model.pkl",
        "models/../model.pkl",
        "../model.pkl",
        "models/model\x00.pkl",
    ],
)
def test_resolve_rejects_invalid_string_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key: str,
) -> None:
    """测试公开解析入口拒绝非法字符串键"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.LOCAL,
        base_dir=tmp_path,
    )

    with pytest.raises(StorageKeyError):
        storage_resolver.resolve(key)


@pytest.mark.parametrize(
    "key",
    [
        None,
        123,
        b"models/model.pkl",
    ],
)
def test_resolve_rejects_non_string_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key: Any,
) -> None:
    """测试公开解析入口拒绝非字符串键"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type=StorageType.LOCAL,
        base_dir=tmp_path,
    )

    with pytest.raises(
        StorageKeyError,
        match="存储键必须是字符串",
    ):
        storage_resolver.resolve(key)


def test_resolve_rejects_unknown_storage_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试拒绝未知存储类型"""
    storage_resolver = create_resolver(
        monkeypatch,
        storage_type="unknown",
        base_dir=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="不支持的存储类型: unknown",
    ):
        storage_resolver.resolve(
            "models/model.pkl"
        )
