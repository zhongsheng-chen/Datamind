# tests/config/test_service.py

"""服务配置测试

验证运行环境必填、可选参数默认值、环境变量读取、
外部配置隔离、参数校验、额外字段处理和配置不可变行为。

核心功能：
  - test_service_config_requires_environment:
    验证运行环境必须显式提供
  - test_service_config_default_optional_values:
    验证服务可选参数默认值
  - test_service_config_ignores_external_sources:
    验证隔离配置不读取外部配置源
  - test_service_config_reads_environment_variables:
    验证从环境变量读取并转换服务配置
  - test_service_config_accepts_custom_values:
    验证接受有效的自定义配置
  - test_service_config_rejects_blank_strings:
    验证拒绝空字符串和纯空白字符串
  - test_service_config_rejects_invalid_port:
    验证拒绝超出范围的监听端口
  - test_service_config_rejects_invalid_numeric_values:
    验证拒绝无效数值参数
  - test_service_config_parses_environment_string:
    验证将字符串解析为运行环境枚举
  - test_service_config_rejects_unknown_environment:
    验证拒绝未知运行环境
  - test_service_config_ignores_extra_fields:
    验证忽略未声明的额外配置字段
  - test_service_config_is_frozen:
    验证服务配置创建后不可修改
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

from datamind.config.service import ServiceConfig
from datamind.constants import Environment


class IsolatedServiceConfig(ServiceConfig):
    """仅使用初始化参数的测试服务配置"""

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
def isolate_service_config(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离服务配置的环境变量和 .env 文件"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_SERVICE_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def create_config(
        **overrides: Any,
) -> ServiceConfig:
    """创建包含必填运行环境的隔离服务配置"""
    config_kwargs: dict[str, Any] = {
        "environment": Environment.DEVELOPMENT,
    }
    config_kwargs.update(overrides)

    return IsolatedServiceConfig(**config_kwargs)


def test_service_config_requires_environment() -> None:
    """测试运行环境必须显式提供"""
    with pytest.raises(ValidationError) as exc_info:
        IsolatedServiceConfig.model_validate({})

    errors = exc_info.value.errors()

    assert errors[0]["loc"] == ("environment",)
    assert errors[0]["type"] == "missing"


def test_service_config_default_optional_values() -> None:
    """测试服务可选参数默认值"""
    config = create_config()

    assert config.name == "datamind"
    assert config.version == "1.0.0"
    assert config.environment == Environment.DEVELOPMENT
    assert config.host == "0.0.0.0"
    assert config.port == 8700
    assert config.workers == 4
    assert config.timeout == 30
    assert config.enable_docs is True
    assert config.enable_health_check is True


def test_service_config_ignores_external_sources(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试隔离配置不读取外部配置源"""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "production",
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_NAME",
        "environment-service",
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "9000",
    )

    config = create_config()

    assert config.environment == Environment.DEVELOPMENT
    assert config.name == "datamind"
    assert config.port == 8700


def test_service_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取并转换服务配置"""
    environment = {
        "DATAMIND_SERVICE_NAME": "datamind-runtime",
        "DATAMIND_SERVICE_VERSION": "2.0.0",
        "DATAMIND_SERVICE_ENVIRONMENT": "production",
        "DATAMIND_SERVICE_HOST": "127.0.0.1",
        "DATAMIND_SERVICE_PORT": "8080",
        "DATAMIND_SERVICE_WORKERS": "8",
        "DATAMIND_SERVICE_TIMEOUT": "60",
        "DATAMIND_SERVICE_ENABLE_DOCS": "false",
        "DATAMIND_SERVICE_ENABLE_HEALTH_CHECK": "false",
    }

    for key, value in environment.items():
        monkeypatch.setenv(
            key,
            value,
        )

    config = ServiceConfig(**{})

    assert config.name == "datamind-runtime"
    assert config.version == "2.0.0"
    assert config.environment == Environment.PRODUCTION
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.workers == 8
    assert config.timeout == 60
    assert config.enable_docs is False
    assert config.enable_health_check is False


def test_service_config_accepts_custom_values() -> None:
    """测试接受有效的自定义配置"""
    config = create_config(
        name="datamind-runtime",
        version="2.0.0",
        environment=Environment.PRODUCTION,
        host="127.0.0.1",
        port=8080,
        workers=8,
        timeout=60,
        enable_docs=False,
        enable_health_check=False,
    )

    assert config.name == "datamind-runtime"
    assert config.version == "2.0.0"
    assert config.environment == Environment.PRODUCTION
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.workers == 8
    assert config.timeout == 60
    assert config.enable_docs is False
    assert config.enable_health_check is False


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error_message",
    ),
    [
        (
            "name",
            "",
            "name 不能为空",
        ),
        (
            "name",
            "   ",
            "name 不能为空",
        ),
        (
            "version",
            "",
            "version 不能为空",
        ),
        (
            "version",
            "   ",
            "version 不能为空",
        ),
        (
            "host",
            "",
            "host 不能为空",
        ),
        (
            "host",
            "   ",
            "host 不能为空",
        ),
    ],
)
def test_service_config_rejects_blank_strings(
        field: str,
        value: str,
        error_message: str,
) -> None:
    """测试拒绝空字符串和纯空白字符串"""
    with pytest.raises(
            ValidationError,
            match=error_message,
    ):
        create_config(
            **{
                field: value,
            }
        )


@pytest.mark.parametrize(
    "port",
    [
        0,
        65536,
    ],
)
def test_service_config_rejects_invalid_port(
        port: int,
) -> None:
    """测试拒绝超出范围的监听端口"""
    with pytest.raises(
            ValidationError,
            match="port 必须在 1 到 65535 之间",
    ):
        create_config(port=port)


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error_message",
    ),
    [
        (
            "workers",
            0,
            "workers 必须大于等于 1",
        ),
        (
            "timeout",
            0,
            "timeout 必须大于等于 1",
        ),
    ],
)
def test_service_config_rejects_invalid_numeric_values(
        field: str,
        value: int | float,
        error_message: str,
) -> None:
    """测试拒绝无效的数值参数"""
    with pytest.raises(
            ValidationError,
            match=error_message,
    ):
        create_config(
            **{
                field: value,
            }
        )


def test_service_config_parses_environment_string() -> None:
    """测试将字符串解析为运行环境枚举"""
    config = create_config(environment="production")

    assert config.environment == Environment.PRODUCTION


def test_service_config_rejects_unknown_environment() -> None:
    """测试拒绝未知运行环境"""
    with pytest.raises(ValidationError):
        create_config(environment="unknown")


def test_service_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段"""
    config = IsolatedServiceConfig.model_validate(
        {
            "environment": Environment.DEVELOPMENT,
            "unknown_option": "ignored",
        }
    )

    assert not hasattr(config, "unknown_option")


def test_service_config_is_frozen() -> None:
    """测试服务配置创建后不可修改"""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "port", 8080)
