"""运行时配置测试.

验证默认值、环境变量读取、参数校验、外部配置隔离和配置不可变行为。

核心功能：
  - test_runtime_config_default_values:
    验证运行时配置默认值
  - test_runtime_config_reads_environment_variables:
    验证从环境变量读取运行时配置
  - test_runtime_config_accepts_custom_values:
    验证接受有效的自定义配置
  - test_runtime_config_rejects_invalid_values:
    验证拒绝无效的协调、心跳和影子执行参数
  - test_runtime_config_is_frozen:
    验证运行时配置不可修改
"""

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.runtime import RuntimeConfig


class IsolatedRuntimeConfig(RuntimeConfig):
    """仅使用初始化参数的测试运行时配置."""

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源."""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        return (init_settings,)


@pytest.fixture(autouse=True)
def isolate_runtime_config(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离运行时环境变量和 .env 文件."""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_RUNTIME_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def create_config(
        **overrides: Any,
) -> RuntimeConfig:
    """创建隔离的运行时配置."""
    return IsolatedRuntimeConfig(
        **overrides
    )


def test_runtime_config_default_values() -> None:
    """测试运行时配置默认值."""
    config = create_config()

    assert config.reconcile_interval == 2.0
    assert config.heartbeat_interval == 30.0
    assert config.shadow_enabled is True
    assert config.shadow_timeout == 5.0


def test_runtime_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取运行时配置."""
    environment = {
        "DATAMIND_RUNTIME_RECONCILE_INTERVAL": "1.5",
        "DATAMIND_RUNTIME_HEARTBEAT_INTERVAL": "15.0",
        "DATAMIND_RUNTIME_SHADOW_ENABLED": "false",
        "DATAMIND_RUNTIME_SHADOW_TIMEOUT": "8.5",
    }

    for key, value in environment.items():
        monkeypatch.setenv(
            key,
            value,
        )

    config = RuntimeConfig()

    assert config.reconcile_interval == 1.5
    assert config.heartbeat_interval == 15.0
    assert config.shadow_enabled is False
    assert config.shadow_timeout == 8.5


def test_runtime_config_accepts_custom_values() -> None:
    """测试接受有效的自定义配置."""
    config = create_config(
        reconcile_interval=1.5,
        heartbeat_interval=15.0,
        shadow_enabled=False,
        shadow_timeout=8.5,
    )

    assert config.reconcile_interval == 1.5
    assert config.heartbeat_interval == 15.0
    assert config.shadow_enabled is False
    assert config.shadow_timeout == 8.5


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "message",
    ),
    [
        (
            "reconcile_interval",
            0,
            "reconcile_interval 必须大于 0",
        ),
        (
            "heartbeat_interval",
            0,
            "heartbeat_interval 必须大于 0",
        ),
        (
            "shadow_timeout",
            0,
            "shadow_timeout 必须大于 0",
        ),
    ],
)
def test_runtime_config_rejects_invalid_values(
        field: str,
        value: int | float,
        message: str,
) -> None:
    """测试拒绝无效的运行时参数."""
    with pytest.raises(
            ValidationError,
            match=message,
    ):
        create_config(
            **{
                field: value,
            }
        )


def test_runtime_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外字段."""
    config = IsolatedRuntimeConfig.model_validate({
        "unknown_option": "ignored",
    })

    assert not hasattr(
        config,
        "unknown_option",
    )


def test_runtime_config_is_frozen() -> None:
    """测试运行时配置不可修改."""
    config = create_config()

    with pytest.raises(ValidationError):
        config.shadow_enabled = False
