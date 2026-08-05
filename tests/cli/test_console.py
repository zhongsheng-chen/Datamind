# tests/cli/test_console.py

"""管理控制台 CLI 测试

验证控制台启动参数、BentoML 子进程和退出状态处理。

核心功能：
  - test_console_run_starts_bentoml_service: 验证启动控制台服务
  - test_console_run_rejects_startup_timeout: 验证服务就绪超时
  - test_console_run_rejects_invalid_port: 验证监听端口
  - test_console_run_propagates_process_error: 验证异常退出码
  - test_console_run_stops_process_on_interrupt: 验证中断处理
"""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import datamind.cli.console.run as run_module
from datamind.cli.main import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_console_readiness(
        monkeypatch: pytest.MonkeyPatch,
) -> MagicMock:
    """替换管理控制台服务就绪检查"""
    wait_until_ready = MagicMock(
        return_value=True
    )
    monkeypatch.setitem(
        vars(run_module),
        "_wait_until_ready",
        wait_until_ready,
    )

    return wait_until_ready


def test_console_run_starts_bentoml_service(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_readiness: MagicMock,
) -> None:
    """测试控制台命令启动独立 BentoML 服务"""
    process = MagicMock()
    process.wait.return_value = 0
    popen = MagicMock(
        return_value=process
    )
    monkeypatch.setitem(
        vars(run_module.subprocess),
        "Popen",
        popen,
    )
    monkeypatch.setitem(
        vars(run_module.sys),
        "executable",
        "python-test",
    )

    result = runner.invoke(
        app,
        [
            "console",
            "run",
            "--host",
            "0.0.0.0",
            "--port",
            "3200",
            "--reload",
        ],
    )

    assert result.exit_code == 0
    assert "Datamind" in result.output
    assert "Powered by Zhongsheng Chen" in result.output
    assert "NAME" in result.output
    assert "datamind" in result.output
    assert "HOST" in result.output
    assert "0.0.0.0" in result.output
    assert "管理控制台正在启动" not in result.output
    assert "管理控制台已启动" not in result.output
    assert "http://127.0.0.1:3200" in result.output
    assert "按 Ctrl+C 停止" in result.output
    mock_console_readiness.assert_called_once_with(
        process,
        "http://127.0.0.1:3200/health",
    )
    popen.assert_called_once_with([
        "python-test",
        "-m",
        "bentoml",
        "serve",
        (
            "datamind.console.service:"
            "DatamindConsoleService"
        ),
        "--host",
        "0.0.0.0",
        "--port",
        "3200",
        "--reload",
    ])


def test_console_run_rejects_invalid_port() -> None:
    """测试控制台命令拒绝非法端口"""
    result = runner.invoke(
        app,
        [
            "console",
            "run",
            "--port",
            "0",
        ],
    )

    assert result.exit_code == 2
    assert "--port 必须在 1 到 65535 之间" in result.output


def test_console_run_rejects_startup_timeout(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务未就绪时不显示访问地址"""
    process = MagicMock()
    process.poll.return_value = None
    process.wait.return_value = 0
    monkeypatch.setitem(
        vars(run_module.subprocess),
        "Popen",
        MagicMock(
            return_value=process
        ),
    )
    monkeypatch.setitem(
        vars(run_module),
        "_wait_until_ready",
        MagicMock(
            return_value=False
        ),
    )

    result = runner.invoke(
        app,
        [
            "console",
            "run",
        ],
    )

    assert result.exit_code == 1
    assert "等待服务就绪超时" in result.output
    assert "访问地址" not in result.output
    process.terminate.assert_called_once_with()


def test_console_run_propagates_process_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台命令返回子进程异常退出码"""
    process = MagicMock()
    process.wait.return_value = 7
    monkeypatch.setitem(
        vars(run_module.subprocess),
        "Popen",
        MagicMock(
            return_value=process
        ),
    )

    result = runner.invoke(
        app,
        [
            "console",
            "run",
        ],
    )

    assert result.exit_code == 7


def test_console_run_stops_process_on_interrupt(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台命令收到中断时终止子进程"""
    process = MagicMock()
    process.wait.side_effect = [
        KeyboardInterrupt,
        0,
    ]
    monkeypatch.setitem(
        vars(run_module.subprocess),
        "Popen",
        MagicMock(
            return_value=process
        ),
    )

    result = runner.invoke(
        app,
        [
            "console",
            "run",
        ],
    )

    assert result.exit_code == 0
    assert "管理控制台已停止" in result.output
    process.terminate.assert_called_once_with()
