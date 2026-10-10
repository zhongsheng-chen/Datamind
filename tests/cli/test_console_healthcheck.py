"""管理控制台健康检查 CLI 测试.

验证公开命令使用配置的探针地址，并通过退出码返回检查结果。

核心功能：
  - test_console_healthcheck_returns_exit_code: 验证健康、不可用和未配置场景
"""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from datamind.cli.main import app
import datamind.cli.common as common_module
import datamind.console.healthcheck as healthcheck_module


runner = CliRunner()


@pytest.mark.parametrize(
    ("url", "available", "expected_exit_code"),
    [
        ("http://console.example/ready", True, 0),
        ("http://console.example/ready", False, 1),
        (None, True, 1),
    ],
)
def test_console_healthcheck_returns_exit_code(
        monkeypatch: pytest.MonkeyPatch,
        url: str | None,
        available: bool,
        expected_exit_code: int,
) -> None:
    """测试健康检查无需登录、保持静默，并返回正确退出码."""
    if url is None:
        monkeypatch.delenv("DATAMIND_HEALTHCHECK_URL", raising=False)
    else:
        monkeypatch.setenv("DATAMIND_HEALTHCHECK_URL", url)

    async def reject_authentication(_context: object) -> None:
        raise AssertionError("console healthcheck 不应进入 CLI 认证上下文")

    urlopen = MagicMock(
        side_effect=None if available else OSError("console unavailable"),
    )
    monkeypatch.setattr(healthcheck_module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(common_module.CLIContext, "__aenter__", reject_authentication)

    result = runner.invoke(app, ["console", "healthcheck"])

    assert result.exit_code == expected_exit_code
    assert result.output == ""
    if url is None:
        urlopen.assert_not_called()
    else:
        urlopen.assert_called_once_with(url, timeout=3.0)
