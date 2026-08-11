# tests/config/test_console.py

"""管理控制台配置测试

验证默认网络参数、环境变量读取、外部配置隔离、参数校验、
额外字段处理和配置不可变行为。

核心功能：
  - test_console_config_default_values: 验证默认网络参数
  - test_console_config_ignores_external_sources: 验证外部配置隔离
  - test_console_config_reads_environment_variables: 验证环境变量读取
  - test_console_config_accepts_custom_values: 验证自定义网络参数
  - test_console_config_rejects_blank_host: 验证监听地址
  - test_console_config_rejects_invalid_port: 验证监听端口
  - test_console_config_ignores_extra_fields: 验证忽略额外字段
  - test_console_config_is_frozen: 验证配置不可变
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.console import ConsoleConfig


class IsolatedConsoleConfig(ConsoleConfig):
    """仅使用初始化参数的测试控制台配置"""

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
def isolate_console_config(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离控制台配置环境变量和 .env 文件"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_CONSOLE_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def test_console_config_default_values() -> None:
    """测试管理控制台默认网络参数"""
    config = IsolatedConsoleConfig()

    assert config.host == "127.0.0.1"
    assert config.port == 8701


def test_console_config_ignores_external_sources(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试隔离配置不读取外部配置源"""
    monkeypatch.setenv(
        "DATAMIND_CONSOLE_HOST",
        "0.0.0.0",
    )
    monkeypatch.setenv(
        "DATAMIND_CONSOLE_PORT",
        "8801",
    )

    config = IsolatedConsoleConfig()

    assert config.host == "127.0.0.1"
    assert config.port == 8701


def test_console_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取控制台网络参数"""
    monkeypatch.setenv(
        "DATAMIND_CONSOLE_HOST",
        "0.0.0.0",
    )
    monkeypatch.setenv(
        "DATAMIND_CONSOLE_PORT",
        "8801",
    )

    config = ConsoleConfig()

    assert config.host == "0.0.0.0"
    assert config.port == 8801


def test_console_config_accepts_custom_values() -> None:
    """测试接受有效的自定义网络参数"""
    config = IsolatedConsoleConfig(
        host="0.0.0.0",
        port=8801,
    )

    assert config.host == "0.0.0.0"
    assert config.port == 8801


@pytest.mark.parametrize(
    "host",
    [
        "",
        "   ",
    ],
)
def test_console_config_rejects_blank_host(
        host: str,
) -> None:
    """测试拒绝空监听地址"""
    with pytest.raises(
            ValidationError,
            match="host 不能为空",
    ):
        IsolatedConsoleConfig(
            host=host
        )


@pytest.mark.parametrize(
    "port",
    [
        0,
        65536,
    ],
)
def test_console_config_rejects_invalid_port(
        port: int,
) -> None:
    """测试拒绝超出范围的监听端口"""
    with pytest.raises(
            ValidationError,
            match="port 必须在 1 到 65535 之间",
    ):
        IsolatedConsoleConfig(
            port=port
        )


def test_console_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段"""
    config = IsolatedConsoleConfig.model_validate(
        {
            "unknown": "value",
        }
    )

    assert not hasattr(
        config,
        "unknown",
    )


def test_console_config_is_frozen() -> None:
    """测试控制台配置创建后不可修改"""
    config = IsolatedConsoleConfig()

    with pytest.raises(
            ValidationError,
            match="Instance is frozen",
    ):
        setattr(
            config,
            "port",
            8801,
        )
