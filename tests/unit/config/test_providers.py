"""子配置 Provider 测试.

验证配置 Provider 能够隔离 Pydantic Settings 的构造细节，并在每次调用时
从当前配置源加载独立对象。

核心功能：
  - test_service_provider_reads_environment:
    验证服务配置 Provider 读取环境变量
  - test_service_provider_requires_environment:
    验证必填运行环境保持必填
  - test_service_provider_returns_fresh_config:
    验证 Provider 不缓存配置并重新读取环境变量
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from datamind.config import get_service_config
from datamind.constants import Environment


@pytest.fixture(autouse=True)
def isolate_service_environment(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离服务配置环境变量和 .env 文件."""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_SERVICE_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def test_service_provider_reads_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务配置 Provider 读取环境变量."""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "production",
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "8800",
    )

    config = get_service_config()

    assert config.environment == Environment.PRODUCTION
    assert config.port == 8800


def test_service_provider_requires_environment() -> None:
    """测试服务配置 Provider 保持运行环境必填."""
    with pytest.raises(ValidationError) as exc_info:
        get_service_config()

    errors = exc_info.value.errors()

    assert errors[0]["loc"] == ("environment",)
    assert errors[0]["type"] == "missing"


def test_service_provider_returns_fresh_config(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务配置 Provider 不缓存环境变量."""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "development",
    )
    first = get_service_config()

    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "testing",
    )
    second = get_service_config()

    assert first is not second
    assert first.environment == Environment.DEVELOPMENT
    assert second.environment == Environment.TESTING
