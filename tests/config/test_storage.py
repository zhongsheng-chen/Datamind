# tests/config/test_storage.py

"""存储配置测试

验证本地存储、MinIO 存储、外部配置隔离、路径安全校验和配置不可变行为。

核心功能：
  - test_local_storage_config_defaults:
    验证本地存储默认配置
  - test_minio_storage_config_defaults:
    验证 MinIO 默认配置
  - test_storage_config_defaults:
    验证顶层存储默认配置
  - test_storage_config_ignores_external_sources:
    验证隔离顶层和嵌套配置的外部配置源
  - test_storage_config_accepts_custom_local_storage:
    验证接受有效的本地存储配置
  - test_storage_config_accepts_valid_minio_storage:
    验证接受凭证完整的 MinIO 配置
  - test_storage_config_rejects_non_positive_max_file_size:
    验证拒绝非正数文件大小上限
  - test_storage_config_rejects_blank_model_dir:
    验证拒绝空模型目录
  - test_storage_config_rejects_absolute_model_dir:
    验证拒绝 Unix、Windows 和 UNC 绝对路径
  - test_storage_config_rejects_parent_directory_reference:
    验证拒绝上级目录引用
  - test_storage_config_accepts_safe_relative_model_dir:
    验证接受安全的相对模型目录
  - test_minio_storage_requires_connection_fields:
    验证 MinIO 存储要求连接字段非空
  - test_local_storage_does_not_require_minio_credentials:
    验证本地存储不要求 MinIO 凭证
  - test_storage_config_parses_storage_type_string:
    验证将字符串解析为存储类型枚举
  - test_storage_config_rejects_unknown_storage_type:
    验证拒绝未知存储类型
  - test_storage_configs_are_frozen:
    验证顶层和嵌套配置创建后不可修改
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.storage import (
    LocalStorageConfig,
    MinIOStorageConfig,
    StorageConfig,
)
from datamind.constants import (
    MB,
    StorageType,
)


class InitOnlySettings:
    """仅保留初始化参数配置源的测试混入类"""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源"""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        return (init_settings,)


class IsolatedLocalStorageConfig(
    InitOnlySettings,
    LocalStorageConfig,
):
    """隔离外部配置源的本地存储配置"""


class IsolatedMinIOStorageConfig(
    InitOnlySettings,
    MinIOStorageConfig,
):
    """隔离外部配置源的 MinIO 存储配置"""


class IsolatedStorageConfig(
    InitOnlySettings,
    StorageConfig,
):
    """隔离外部配置源的存储配置"""


def create_local_config(
        **overrides: Any,
) -> LocalStorageConfig:
    """创建隔离外部配置源的本地存储配置"""
    return IsolatedLocalStorageConfig(**overrides)


def create_minio_config(
        **overrides: Any,
) -> MinIOStorageConfig:
    """创建隔离外部配置源的 MinIO 存储配置"""
    return IsolatedMinIOStorageConfig(**overrides)


def create_storage_config(
        **overrides: Any,
) -> StorageConfig:
    """创建隔离外部配置源的存储配置"""
    config_kwargs: dict[str, Any] = {
        "local": create_local_config(),
        "minio": create_minio_config(),
    }
    config_kwargs.update(overrides)

    return IsolatedStorageConfig(**config_kwargs)


def create_valid_minio_config(
        **overrides: Any,
) -> MinIOStorageConfig:
    """创建凭证完整的 MinIO 测试配置"""
    config_kwargs: dict[str, Any] = {
        "endpoint": "minio.internal:9000",
        "bucket": "datamind-models",
        "access_key": "datamind",
        "secret_key": "datamind-secret",
        "secure": True,
        "region": "cn-north-1",
        "base_prefix": "models",
    }
    config_kwargs.update(overrides)

    return create_minio_config(**config_kwargs)


def test_local_storage_config_defaults() -> None:
    """测试本地存储默认配置"""
    config = create_local_config()

    assert config.base_dir == Path("./data")


def test_minio_storage_config_defaults() -> None:
    """测试 MinIO 默认配置"""
    config = create_minio_config()

    assert config.endpoint == "localhost:9000"
    assert config.bucket == "datamind"
    assert config.access_key == ""
    assert config.secret_key == ""
    assert config.secure is False
    assert config.region is None
    assert config.base_prefix == "datamind"


def test_storage_config_defaults() -> None:
    """测试存储配置默认值"""
    config = create_storage_config()

    assert config.type == StorageType.LOCAL
    assert config.max_file_size == 200 * MB
    assert config.model_dir == "models"
    assert config.local.base_dir == Path("./data")
    assert config.minio.endpoint == "localhost:9000"


def test_storage_config_ignores_external_sources(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试隔离顶层和嵌套配置的外部配置源"""
    monkeypatch.setenv(
        "DATAMIND_STORAGE_TYPE",
        "minio",
    )
    monkeypatch.setenv(
        "DATAMIND_STORAGE_MAX_FILE_SIZE",
        "1",
    )
    monkeypatch.setenv(
        "DATAMIND_STORAGE_MODEL_DIR",
        "environment-models",
    )
    monkeypatch.setenv(
        "DATAMIND_STORAGE_LOCAL_BASE_DIR",
        "/environment/data",
    )
    monkeypatch.setenv(
        "DATAMIND_STORAGE_MINIO_ENDPOINT",
        "environment:9000",
    )

    config = create_storage_config()

    assert config.type == StorageType.LOCAL
    assert config.max_file_size == 200 * MB
    assert config.model_dir == "models"
    assert config.local.base_dir == Path("./data")
    assert config.minio.endpoint == "localhost:9000"


def test_storage_config_accepts_custom_local_storage(
        tmp_path: Path,
) -> None:
    """测试接受有效的本地存储配置"""
    local = create_local_config(
        base_dir=tmp_path / "model-data"
    )

    config = create_storage_config(
        type=StorageType.LOCAL,
        max_file_size=500 * MB,
        model_dir="registry/models",
        local=local,
    )

    assert config.type == StorageType.LOCAL
    assert config.max_file_size == 500 * MB
    assert config.model_dir == "registry/models"
    assert config.local.base_dir == tmp_path / "model-data"


def test_storage_config_accepts_valid_minio_storage() -> None:
    """测试接受凭证完整的 MinIO 配置"""
    minio = create_valid_minio_config()

    config = create_storage_config(
        type=StorageType.MINIO,
        model_dir="registry/models",
        minio=minio,
    )

    assert config.type == StorageType.MINIO
    assert config.minio.endpoint == "minio.internal:9000"
    assert config.minio.bucket == "datamind-models"
    assert config.minio.access_key == "datamind"
    assert config.minio.secret_key == "datamind-secret"
    assert config.minio.secure is True
    assert config.minio.region == "cn-north-1"
    assert config.minio.base_prefix == "models"


@pytest.mark.parametrize(
    "max_file_size",
    [
        0,
        -1,
    ],
)
def test_storage_config_rejects_non_positive_max_file_size(
        max_file_size: int,
) -> None:
    """测试拒绝非正数文件大小上限"""
    with pytest.raises(
            ValidationError,
            match="max_file_size 必须大于 0",
    ):
        create_storage_config(
            max_file_size=max_file_size
        )


@pytest.mark.parametrize(
    "model_dir",
    [
        "",
        "   ",
    ],
)
def test_storage_config_rejects_blank_model_dir(
        model_dir: str,
) -> None:
    """测试拒绝空模型目录"""
    with pytest.raises(
            ValidationError,
            match="model_dir 不能为空",
    ):
        create_storage_config(model_dir=model_dir)


@pytest.mark.parametrize(
    "model_dir",
    [
        "/models",
        "C:/models",
        r"C:\models",
        r"\\server\share\models",
    ],
)
def test_storage_config_rejects_absolute_model_dir(
        model_dir: str,
) -> None:
    """测试拒绝 Unix、Windows 和 UNC 绝对路径"""
    with pytest.raises(
            ValidationError,
            match="model_dir 必须是相对目录",
    ):
        create_storage_config(model_dir=model_dir)


@pytest.mark.parametrize(
    "model_dir",
    [
        "../models",
        "registry/../models",
        r"registry\..\models",
    ],
)
def test_storage_config_rejects_parent_directory_reference(
        model_dir: str,
) -> None:
    """测试拒绝包含上级目录引用的模型目录"""
    with pytest.raises(
            ValidationError,
            match="model_dir 不能包含上级目录引用",
    ):
        create_storage_config(model_dir=model_dir)


@pytest.mark.parametrize(
    "model_dir",
    [
        "models",
        "registry/models",
        r"registry\models",
    ],
)
def test_storage_config_accepts_safe_relative_model_dir(
        model_dir: str,
) -> None:
    """测试接受安全的相对模型目录"""
    config = create_storage_config(model_dir=model_dir)

    assert config.model_dir == model_dir


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error_message",
    ),
    [
        (
            "endpoint",
            "   ",
            "endpoint 不能为空",
        ),
        (
            "bucket",
            "   ",
            "bucket 不能为空",
        ),
        (
            "access_key",
            "   ",
            "access_key 不能为空",
        ),
        (
            "secret_key",
            "   ",
            "secret_key 不能为空",
        ),
    ],
)
def test_minio_storage_requires_connection_fields(
        field: str,
        value: str,
        error_message: str,
) -> None:
    """测试 MinIO 存储要求连接字段非空"""
    minio = create_valid_minio_config(
        **{
            field: value,
        }
    )

    with pytest.raises(
            ValidationError,
            match=error_message,
    ):
        create_storage_config(
            type=StorageType.MINIO,
            minio=minio,
        )


def test_local_storage_does_not_require_minio_credentials() -> None:
    """测试本地存储不要求填写 MinIO 凭证"""
    config = create_storage_config(
        type=StorageType.LOCAL,
        minio=create_minio_config(),
    )

    assert config.type == StorageType.LOCAL
    assert config.minio.access_key == ""
    assert config.minio.secret_key == ""


def test_storage_config_parses_storage_type_string() -> None:
    """测试将字符串解析为存储类型枚举"""
    config = create_storage_config(type="local")

    assert config.type == StorageType.LOCAL


def test_storage_config_rejects_unknown_storage_type() -> None:
    """测试拒绝未知存储类型"""
    with pytest.raises(ValidationError):
        create_storage_config(type="unknown")


def test_storage_configs_are_frozen() -> None:
    """测试顶层和嵌套存储配置创建后不可修改"""
    config = create_storage_config()

    with pytest.raises(ValidationError):
        config.model_dir = "new-models"

    with pytest.raises(ValidationError):
        config.local.base_dir = Path("./new-data")

    with pytest.raises(ValidationError):
        config.minio.endpoint = "new-endpoint:9000"
