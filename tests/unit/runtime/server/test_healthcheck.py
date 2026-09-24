"""运行时服务健康检查测试.

验证健康检查请求和服务不可用时的失败结果。

核心功能：
  - test_healthcheck_calls_ready_endpoint:
    验证健康检查使用约定的就绪接口
  - test_healthcheck_handles_unavailable_service:
    验证服务不可用时返回健康检查失败
"""

from unittest.mock import MagicMock

import pytest

import datamind.runtime.server.entrypoints.healthcheck as healthcheck_module


def test_healthcheck_calls_ready_endpoint(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试健康检查使用约定的就绪接口."""
    monkeypatch.setenv(
        "DATAMIND_HEALTHCHECK_URL",
        "http://runtime.example/ready",
    )
    urlopen = MagicMock()
    monkeypatch.setattr(
        healthcheck_module.urllib.request,
        "urlopen",
        urlopen,
    )

    assert healthcheck_module.is_runtime_ready()

    request = urlopen.call_args.args[0]
    assert request.full_url == "http://runtime.example/ready"
    assert request.get_method() == "POST"
    assert request.data == b"{}"
    assert request.get_header("Content-type") == "application/json"
    assert urlopen.call_args.kwargs == {"timeout": 3.0}


def test_healthcheck_handles_unavailable_service(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务不可用时返回健康检查失败."""
    monkeypatch.setenv(
        "DATAMIND_HEALTHCHECK_URL",
        "http://runtime.example/ready",
    )
    monkeypatch.setattr(
        healthcheck_module.urllib.request,
        "urlopen",
        MagicMock(side_effect=OSError("service unavailable")),
    )

    assert not healthcheck_module.is_runtime_ready()
