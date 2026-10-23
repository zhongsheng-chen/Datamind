"""预测服务和任务 Worker 健康检查 CLI 测试.

验证健康检查命令无需登录，并通过退出码返回检查结果。

核心功能：
  - test_healthcheck_returns_exit_code: 验证就绪与失败结果
"""

import importlib
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from datamind.cli.main import app
import datamind.cli.common as common_module


runner = CliRunner()


@pytest.mark.parametrize(
    ("component", "module_name", "predicate"),
    [
        ("service", "datamind.cli.service.healthcheck", "is_runtime_ready"),
        ("worker", "datamind.runtime.task_queue.healthcheck", "is_worker_ready"),
    ],
)
@pytest.mark.parametrize("ready", [True, False])
def test_healthcheck_returns_exit_code(
        monkeypatch: pytest.MonkeyPatch,
        component: str,
        module_name: str,
        predicate: str,
        ready: bool,
) -> None:
    """测试检查命令保持静默，无需认证并返回对应退出码."""
    module = importlib.import_module(module_name)
    check = MagicMock(return_value=ready)
    monkeypatch.setattr(module, predicate, check)

    async def reject_authentication(_context: object) -> None:
        raise AssertionError("healthcheck 不应进入 CLI 认证上下文")

    monkeypatch.setattr(common_module.CLIContext, "__aenter__", reject_authentication)

    result = runner.invoke(app, [component, "healthcheck"])

    assert result.exit_code == (0 if ready else 1)
    assert result.output == ""
    check.assert_called_once_with()
