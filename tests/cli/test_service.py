# tests/cli/test_service.py

"""模型服务 CLI 测试

验证模型服务进程启动不依赖本地 CLI 登录会话。

核心功能：
  - test_service_run_does_not_authenticate_cli_user:
    验证服务启动不执行用户认证
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)
import importlib

import pytest
from typer.testing import CliRunner

import datamind.cli.common as common_module
from datamind.cli.main import app


run_module = importlib.import_module(
    "datamind.cli.service.run"
)
runner = CliRunner()


def test_service_run_does_not_authenticate_cli_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务启动不执行用户认证"""
    async def reject_authentication(
            _context: object,
    ) -> None:
        raise AssertionError(
            "service run 不应进入 CLI 认证上下文"
        )

    process = MagicMock(
        pid=12345,
    )
    process.wait.return_value = 0
    process.poll.return_value = None
    popen = MagicMock(
        return_value=process
    )

    settings = SimpleNamespace(
        logging=MagicMock(),
        service=SimpleNamespace(
            name="datamind",
            environment="development",
            host="127.0.0.1",
            port=8700,
            workers=1,
        ),
    )

    monkeypatch.setattr(
        common_module.CLIContext,
        "__aenter__",
        reject_authentication,
    )
    monkeypatch.setitem(
        vars(run_module),
        "get_settings",
        lambda: settings,
    )
    monkeypatch.setitem(
        vars(run_module),
        "setup_logging",
        lambda _config: None,
    )
    monkeypatch.setitem(
        vars(run_module),
        "shutdown_logging",
        lambda: None,
    )
    monkeypatch.setitem(
        vars(run_module.subprocess),
        "Popen",
        popen,
    )
    monkeypatch.setitem(
        vars(run_module),
        "_build_ready_dir",
        lambda _service_instance_id: (
            Path("runtime_ready_test")
        ),
    )
    monkeypatch.setitem(
        vars(run_module),
        "_prepare_ready_dir",
        lambda _ready_dir: None,
    )
    monkeypatch.setitem(
        vars(run_module),
        "_cleanup_ready_dir",
        lambda _ready_dir: None,
    )
    monkeypatch.setitem(
        vars(run_module),
        "_wait_for_workers_ready",
        AsyncMock(
            return_value={
                "worker_test"
            }
        ),
    )

    result = runner.invoke(
        app,
        [
            "service",
            "run",
        ],
    )

    assert result.exit_code == 0
    assert "认证失败" not in result.output
    assert "NAME" not in result.output
    assert "ENVIRONMENT" in result.output
    assert "development" in result.output
    assert "BIND" in result.output
    assert "127.0.0.1:8700" in result.output
    assert "URL" in result.output
    assert "http://127.0.0.1:8700" in result.output
    assert "WORKERS" in result.output
    assert "RELOAD" in result.output
    assert "disabled" in result.output
    assert "PID" in result.output
    assert "12345" in result.output
    assert "Press Ctrl+C to stop" in result.output
    command = popen.call_args.args[0]
    assert "--quiet" in command
