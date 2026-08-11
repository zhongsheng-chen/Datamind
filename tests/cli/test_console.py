# tests/cli/test_console.py

"""管理控制台 CLI 测试

验证控制台启动参数、BentoML 子进程和退出状态处理。

核心功能：
  - test_wait_for_console_ready_uses_direct_http_connection: 验证直接探测服务
  - test_wait_for_console_ready_rejects_non_ready_response: 验证未就绪响应
  - test_console_run_starts_bentoml_service: 验证启动控制台服务
  - test_console_run_uses_configured_network: 验证读取控制台网络配置
  - test_console_run_rejects_startup_timeout: 验证服务就绪超时
  - test_console_run_rejects_invalid_port: 验证监听端口
  - test_console_run_propagates_process_error: 验证异常退出码
  - test_console_run_stops_process_on_interrupt: 验证中断处理
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import datamind.cli.console.run as run_module
from datamind.cli.main import app


runner = CliRunner()
WAIT_FOR_CONSOLE_READY = run_module.wait_for_console_ready


@pytest.fixture(autouse=True)
def mock_console_settings(
        monkeypatch: pytest.MonkeyPatch,
) -> SimpleNamespace:
    """替换管理控制台和服务配置"""
    settings = SimpleNamespace(
        console=SimpleNamespace(
            host="127.0.0.1",
            port=8701,
        ),
        service=SimpleNamespace(
            environment="development",
        ),
    )
    monkeypatch.setitem(
        vars(run_module),
        "get_settings",
        lambda: settings,
    )

    return settings


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
        "wait_for_console_ready",
        wait_until_ready,
    )

    return wait_until_ready


def test_wait_for_console_ready_uses_direct_http_connection(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试就绪检查直接连接管理控制台"""
    process = MagicMock()
    process.poll.return_value = None
    response = MagicMock(
        status=200
    )
    connection = MagicMock()
    connection.getresponse.return_value = response
    connection_factory = MagicMock(
        return_value=connection
    )
    monkeypatch.setitem(
        vars(run_module),
        "HTTPConnection",
        connection_factory,
    )

    assert WAIT_FOR_CONSOLE_READY(
        process,
        "http://127.0.0.1:8701/health",
    )
    connection_factory.assert_called_once_with(
        host="127.0.0.1",
        port=8701,
        timeout=1.0,
    )
    connection.request.assert_called_once_with(
        "GET",
        "/health",
        headers={
            "Connection": "close",
        },
    )
    response.read.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_wait_for_console_ready_rejects_non_ready_response(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务异常响应不会被判定为就绪"""
    process = MagicMock()
    process.poll.side_effect = [
        None,
        1,
    ]
    response = MagicMock(
        status=404
    )
    connection = MagicMock()
    connection.getresponse.return_value = response
    monkeypatch.setitem(
        vars(run_module),
        "HTTPConnection",
        MagicMock(
            return_value=connection
        ),
    )
    monkeypatch.setitem(
        vars(run_module.time),
        "sleep",
        MagicMock(),
    )

    assert not WAIT_FOR_CONSOLE_READY(
        process,
        "http://127.0.0.1:8701/health",
    )
    connection.close.assert_called_once_with()


def test_console_run_starts_bentoml_service(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_readiness: MagicMock,
) -> None:
    """测试控制台命令启动独立 BentoML 服务"""
    process = MagicMock()
    process.pid = 4321
    process.wait.return_value = 0
    popen = MagicMock(
        return_value=process
    )
    structured_logger = MagicMock()
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
    monkeypatch.setitem(
        vars(run_module),
        "logger",
        structured_logger,
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
    assert "Datamind v0.1.0" in result.output
    assert "Powered by Zhongsheng Chen" in result.output
    assert "NAME" not in result.output
    assert "ENVIRONMENT" in result.output
    assert "development" in result.output
    assert "BIND" in result.output
    assert "0.0.0.0:3200" in result.output
    assert "URL" in result.output
    assert "http://127.0.0.1:3200" in result.output
    assert "RELOAD" in result.output
    assert "enabled" in result.output
    assert "PID" in result.output
    assert "4321" in result.output
    assert "STATUS" not in result.output
    assert "HEALTH" not in result.output
    assert "Press Ctrl+C to stop" in result.output
    completed_events = [
        keyword_arguments
        for positional_arguments, keyword_arguments
        in structured_logger.info.call_args_list
        if positional_arguments == (
            "管理控制台启动完成",
        )
    ]
    assert len(completed_events) == 1
    completed_event = completed_events[0]
    assert completed_event == {
        "service_name": "datamind_console_service",
        "version": "0.1.0",
        "environment": "development",
        "bind": "0.0.0.0:3200",
        "url": "http://127.0.0.1:3200",
        "reload": True,
        "pid": 4321,
    }
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
        "--quiet",
    ])


def test_console_run_uses_configured_network(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_settings: SimpleNamespace,
        mock_console_readiness: MagicMock,
) -> None:
    """测试未传网络参数时读取控制台配置"""
    mock_console_settings.console.host = "0.0.0.0"
    mock_console_settings.console.port = 8801
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
        ],
    )

    assert result.exit_code == 0
    assert "http://127.0.0.1:8801" in result.output
    assert "disabled" in result.output
    mock_console_readiness.assert_called_once_with(
        process,
        "http://127.0.0.1:8801/health",
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
        "8801",
        "--quiet",
    ])


def test_console_run_verbose_preserves_bentoml_logs(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试详细模式不抑制 BentoML 日志"""
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

    result = runner.invoke(
        app,
        [
            "console",
            "run",
            "--verbose",
        ],
    )

    assert result.exit_code == 0
    command = popen.call_args.args[0]
    assert "--quiet" not in command


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
    """测试服务未就绪时不显示就绪状态"""
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
    wait_until_ready = MagicMock(
        return_value=False
    )
    monkeypatch.setitem(
        vars(run_module),
        "wait_for_console_ready",
        wait_until_ready,
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
    assert "Powered by Zhongsheng Chen" not in result.output
    wait_until_ready.assert_called_once_with(
        process,
        "http://127.0.0.1:8701/health",
    )
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
