"""管理控制台健康检查测试.

验证健康检查地址和服务不可用时的失败结果。

核心功能：
  - test_healthcheck_calls_configured_endpoint:
    验证健康检查使用容器配置的地址
  - test_healthcheck_handles_unavailable_console:
    验证控制台不可用时返回健康检查失败
"""

from unittest.mock import MagicMock

import pytest

import datamind.console.healthcheck as healthcheck_module


def test_healthcheck_calls_configured_endpoint(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试健康检查使用容器配置的地址."""
    monkeypatch.setenv(
        "DATAMIND_HEALTHCHECK_URL",
        "http://console.example/ready",
    )
    urlopen = MagicMock()
    monkeypatch.setattr(
        healthcheck_module.urllib.request,
        "urlopen",
        urlopen,
    )

    assert healthcheck_module.is_console_healthy()
    urlopen.assert_called_once_with(
        "http://console.example/ready",
        timeout=3.0,
    )


def test_healthcheck_handles_unavailable_console(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台不可用时返回健康检查失败."""
    monkeypatch.setenv(
        "DATAMIND_HEALTHCHECK_URL",
        "http://console.example/ready",
    )
    monkeypatch.setattr(
        healthcheck_module.urllib.request,
        "urlopen",
        MagicMock(side_effect=OSError("console unavailable")),
    )

    assert not healthcheck_module.is_console_healthy()
