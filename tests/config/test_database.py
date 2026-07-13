# tests/config/test_database.py

"""数据库配置测试

验证数据库 URL 必填、默认参数、自定义参数、环境变量读取、
外部配置隔离、参数校验和配置不可变行为。

核心功能：
  - test_database_config_requires_url:
    验证数据库连接 URL 必须显式提供
  - test_database_config_default_optional_values:
    验证数据库可选参数默认值
  - test_database_config_ignores_external_sources:
    验证隔离配置不读取外部配置源
  - test_database_config_reads_environment_variables:
    验证从环境变量读取并转换数据库配置
  - test_database_config_accepts_custom_values:
    验证接受有效的自定义配置
  - test_database_config_allows_zero_pool_values:
    验证连接池数值允许为零
  - test_database_config_rejects_blank_url:
    验证拒绝空白数据库连接 URL
  - test_database_config_rejects_negative_values:
    验证拒绝负数连接池参数
  - test_database_config_ignores_extra_fields:
    验证忽略未声明的额外配置字段
  - test_database_config_is_frozen:
    验证数据库配置创建后不可修改
"""

import os
from pathlib import Path
from typing import (
    Any,
    Final,
)

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.database import DatabaseConfig


TEST_DATABASE_URL: Final[str] = (
    "postgresql+asyncpg://test:test@localhost:5432/datamind_test"
)


class IsolatedDatabaseConfig(DatabaseConfig):
    """仅使用初始化参数的测试数据库配置"""

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


@pytest.fixture(autouse=True)
def clear_database_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清除数据库配置相关环境变量"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_DATABASE_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )


def create_config(
        **overrides: Any,
) -> DatabaseConfig:
    """创建隔离外部配置源的数据库配置"""
    config_kwargs: dict[str, Any] = {
        "url": TEST_DATABASE_URL,
    }
    config_kwargs.update(overrides)

    return IsolatedDatabaseConfig(**config_kwargs)


def test_database_config_requires_url() -> None:
    """测试数据库连接 URL 必须显式提供"""
    with pytest.raises(
            ValidationError,
            match="url 不能为空",
    ):
        IsolatedDatabaseConfig()


def test_database_config_default_optional_values() -> None:
    """测试数据库可选参数默认值"""
    config = create_config()

    assert config.url == TEST_DATABASE_URL
    assert config.pool_size == 10
    assert config.max_overflow == 20
    assert config.pool_timeout == 30
    assert config.pool_recycle == 3600
    assert config.echo is False


def test_database_config_ignores_external_sources(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试隔离环境变量配置源"""
    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL",
        "postgresql+asyncpg://env:secret@db:5432/env",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_POOL_SIZE",
        "50",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_ECHO",
        "true",
    )

    config = create_config()

    assert config.url == TEST_DATABASE_URL
    assert config.pool_size == 10
    assert config.echo is False


def test_database_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试从环境变量读取并转换数据库配置"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL",
        "postgresql+asyncpg://app:secret@db:5432/datamind",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_POOL_SIZE",
        "25",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_MAX_OVERFLOW",
        "15",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_POOL_TIMEOUT",
        "45",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_POOL_RECYCLE",
        "1800",
    )
    monkeypatch.setenv(
        "DATAMIND_DATABASE_ECHO",
        "true",
    )

    config = DatabaseConfig()

    assert config.url == "postgresql+asyncpg://app:secret@db:5432/datamind"
    assert config.pool_size == 25
    assert config.max_overflow == 15
    assert config.pool_timeout == 45
    assert config.pool_recycle == 1800
    assert config.echo is True


def test_database_config_accepts_custom_values() -> None:
    """测试接受有效的自定义配置"""
    config = create_config(
        url="postgresql+asyncpg://app:secret@db:5432/datamind",
        pool_size=30,
        max_overflow=10,
        pool_timeout=60,
        pool_recycle=900,
        echo=True,
    )

    assert config.url == "postgresql+asyncpg://app:secret@db:5432/datamind"
    assert config.pool_size == 30
    assert config.max_overflow == 10
    assert config.pool_timeout == 60
    assert config.pool_recycle == 900
    assert config.echo is True


def test_database_config_allows_zero_pool_values() -> None:
    """测试连接池数值允许为零"""
    config = create_config(
        pool_size=0,
        max_overflow=0,
        pool_timeout=0,
        pool_recycle=0,
    )

    assert config.pool_size == 0
    assert config.max_overflow == 0
    assert config.pool_timeout == 0
    assert config.pool_recycle == 0


@pytest.mark.parametrize(
    "url",
    [
        "",
        " ",
        "   ",
        "\t",
        "\n",
    ],
)
def test_database_config_rejects_blank_url(
        url: str,
) -> None:
    """测试数据库连接 URL 不能为空白字符串"""
    with pytest.raises(
            ValidationError,
            match="url 不能为空",
    ):
        create_config(url=url)


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error_message",
    ),
    [
        (
            "pool_size",
            -1,
            "pool_size 必须大于等于 0",
        ),
        (
            "max_overflow",
            -1,
            "max_overflow 必须大于等于 0",
        ),
        (
            "pool_timeout",
            -1,
            "pool_timeout 必须大于等于 0",
        ),
        (
            "pool_recycle",
            -1,
            "pool_recycle 必须大于等于 0",
        ),
    ],
)
def test_database_config_rejects_negative_values(
        field: str,
        value: int,
        error_message: str,
) -> None:
    """测试数据库数值参数不能为负数"""
    with pytest.raises(
            ValidationError,
            match=error_message,
    ):
        create_config(
            **{
                field: value,
            }
        )


def test_database_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段"""
    config = create_config(
        unknown_option="ignored",
    )

    assert not hasattr(config, "unknown_option")


def test_database_config_is_frozen() -> None:
    """测试数据库配置创建后不可修改"""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "pool_size", 20)
