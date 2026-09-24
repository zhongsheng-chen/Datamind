"""管理控制台 CLI 测试.

验证控制台启动参数、BentoML 子进程和退出状态处理。

核心功能：
  - test_console_run_rejects_invalid_timeout:
    验证启动超时参数范围
  - test_stop_console_process_on_windows:
    验证 Windows 定向清理进程树
  - test_stop_console_process_reports_failure:
    验证清理失败可见
  - test_stop_console_process_on_posix:
    验证独立进程组清理
  - test_wait_for_console_ready_uses_direct_http_connection:
    验证直接探测服务
  - test_wait_for_console_ready_rejects_non_ready_response:
    验证未就绪响应
  - test_wait_for_console_ready_reports_last_failure:
    验证超时日志保留失败原因
  - test_console_run_starts_bentoml_service:
    验证启动控制台服务
  - test_console_run_uses_configured_network:
    验证读取控制台网络配置
  - test_console_run_rejects_startup_timeout:
    验证服务就绪超时
  - test_console_run_rejects_invalid_port:
    验证监听端口
  - test_console_run_propagates_process_error:
    验证异常退出码
  - test_console_run_stops_process_on_interrupt:
    验证中断处理
"""

from types import SimpleNamespace
from unittest.mock import (
    ANY,
    MagicMock,
)

import pytest
from click import unstyle
from typer.testing import CliRunner

import datamind.cli.console.run as run_module
from datamind.cli.main import app
from datamind.constants import Environment


runner = CliRunner()
WAIT_FOR_CONSOLE_READY = run_module.wait_for_console_ready
STOP_CONSOLE_PROCESS = run_module.stop_console_process


@pytest.fixture(autouse=True)
def mock_console_stop(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """隔离进程树清理，避免测试停止真实进程."""
    stop = MagicMock(return_value=True)
    monkeypatch.setitem(vars(run_module), "stop_console_process", stop)
    return stop


@pytest.fixture(autouse=True)
def mock_console_settings(
        monkeypatch: pytest.MonkeyPatch,
) -> SimpleNamespace:
    """替换管理控制台和服务配置."""
    settings = SimpleNamespace(
        console=SimpleNamespace(
            host="127.0.0.1",
            port=8701,
            startup_timeout=120,
        ),
        service=SimpleNamespace(
            environment=Environment.DEVELOPMENT,
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
    """替换管理控制台服务就绪检查."""
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
    """测试就绪检查直接连接管理控制台."""
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
        vars(run_module.time),
        "monotonic",
        MagicMock(side_effect=[0.0, 45.0]),
    )
    monkeypatch.setitem(
        vars(run_module),
        "HTTPConnection",
        connection_factory,
    )

    assert WAIT_FOR_CONSOLE_READY(
        process,
        "http://127.0.0.1:8701/ready",
        timeout_seconds=90,
    )
    connection_factory.assert_called_once_with(
        host="127.0.0.1",
        port=8701,
        timeout=1.0,
    )
    connection.request.assert_called_once_with(
        "GET",
        "/ready",
        headers={
            "Connection": "close",
        },
    )
    response.read.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_wait_for_console_ready_rejects_non_ready_response(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务异常响应不会被判定为就绪."""
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
        "http://127.0.0.1:8701/ready",
        timeout_seconds=120,
    )
    connection.close.assert_called_once_with()


def test_wait_for_console_ready_reports_last_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试就绪探测超时日志保留最后一次失败原因."""
    process = MagicMock()
    process.poll.return_value = None
    connection = MagicMock()
    connection.request.side_effect = OSError("connection refused")
    structured_logger = MagicMock()
    monkeypatch.setitem(
        vars(run_module),
        "HTTPConnection",
        MagicMock(return_value=connection),
    )
    monkeypatch.setitem(
        vars(run_module.time),
        "monotonic",
        MagicMock(side_effect=[0.0, 0.0, 2.0]),
    )
    monkeypatch.setitem(
        vars(run_module.time),
        "sleep",
        MagicMock(),
    )
    monkeypatch.setitem(
        vars(run_module),
        "logger",
        structured_logger,
    )

    assert not WAIT_FOR_CONSOLE_READY(
        process,
        "http://127.0.0.1:8701/ready",
        timeout_seconds=1,
    )
    structured_logger.warning.assert_called_once_with(
        "Datamind 管理控制台就绪探测超时",
        readiness_url="http://127.0.0.1:8701/ready",
        timeout_seconds=1,
        last_failure="OSError: connection refused",
    )
    connection.close.assert_called_once_with()


def test_console_run_starts_bentoml_service(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_readiness: MagicMock,
) -> None:
    """测试控制台命令启动独立 BentoML 服务."""
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
            "--startup-timeout",
            "180",
        ],
    )

    assert result.exit_code == 0
    output = unstyle(result.output)
    assert "Datamind v0.1.0" in output
    assert "Powered by Zhongsheng Chen" in output
    assert "NAME" not in output
    assert "ENVIRONMENT" in output
    assert "development" in output
    assert "BIND" in output
    assert "0.0.0.0:3200" in output
    assert "URL" in output
    assert "http://127.0.0.1:3200" in output
    assert "RELOAD" in output
    assert "enabled" in output
    assert "PID" in output
    assert "4321" in output
    assert "STATUS" not in output
    assert "HEALTH" not in output
    assert "Press Ctrl+C to stop" in output
    completed_events = [
        keyword_arguments
        for positional_arguments, keyword_arguments
        in structured_logger.info.call_args_list
        if positional_arguments == (
            "Datamind 管理控制台启动完成",
        )
    ]
    assert len(completed_events) == 1
    completed_event = completed_events[0]
    child_instance_id = popen.call_args.kwargs["env"]["DATAMIND_SERVICE_INSTANCE_ID"]
    assert len(child_instance_id) == 32
    assert completed_event == {
        "elapsed_seconds": ANY,
        "service_instance_id": child_instance_id,
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
        "http://127.0.0.1:3200/ready",
        timeout_seconds=180,
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
    ], env=ANY, start_new_session=ANY)


@pytest.mark.parametrize("timeout_override", [None, 180])
def test_console_run_uses_configured_network(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_settings: SimpleNamespace,
        mock_console_readiness: MagicMock,
        timeout_override: int | None,
) -> None:
    """测试未传网络参数时读取控制台配置."""
    mock_console_settings.console.host = "0.0.0.0"
    mock_console_settings.console.port = 8801
    mock_console_settings.console.startup_timeout = 240
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
            *(
                ["--startup-timeout", str(timeout_override)]
                if timeout_override is not None else []
            ),
        ],
    )

    assert result.exit_code == 0
    assert "http://127.0.0.1:8801" in result.output
    assert "disabled" in result.output
    mock_console_readiness.assert_called_once_with(
        process,
        "http://127.0.0.1:8801/ready",
        timeout_seconds=timeout_override if timeout_override is not None else 240,
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
    ], env=ANY, start_new_session=ANY)


def test_console_run_verbose_preserves_bentoml_logs(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试详细模式不抑制 BentoML 日志."""
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


@pytest.mark.parametrize("timeout", ["0", "601"])
def test_console_run_rejects_invalid_timeout(timeout: str) -> None:
    """测试启动等待时间必须在支持范围内."""
    result = runner.invoke(app, ["console", "run", "--startup-timeout", timeout])
    assert result.exit_code == 2
    assert "--startup-timeout" in unstyle(result.output)


def test_stop_console_process_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试只清理本次启动的 PID 及其后代进程."""
    process = MagicMock(pid=4321)
    terminate_tree = MagicMock()
    monkeypatch.setitem(vars(run_module.sys), "platform", "win32")
    monkeypatch.setitem(vars(run_module.subprocess), "run", terminate_tree)
    monkeypatch.setitem(vars(run_module.subprocess), "CREATE_NO_WINDOW", 0x08000000)

    assert STOP_CONSOLE_PROCESS(process) is True
    terminate_tree.assert_called_once_with(
        ["taskkill", "/PID", "4321", "/T", "/F"],
        check=True,
        capture_output=True,
        timeout=10,
        creationflags=0x08000000,
    )
    process.wait.assert_called_once_with(timeout=10)


def test_stop_console_process_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试进程树清理失败时不报告停止成功."""
    process = MagicMock(pid=4321)
    terminate_tree = MagicMock(side_effect=OSError("access denied"))
    monkeypatch.setitem(vars(run_module.sys), "platform", "win32")
    monkeypatch.setitem(vars(run_module.subprocess), "run", terminate_tree)
    monkeypatch.setitem(vars(run_module.subprocess), "CREATE_NO_WINDOW", 0x08000000)

    assert STOP_CONSOLE_PROCESS(process) is False
    process.wait.assert_not_called()


def test_stop_console_process_on_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试停止独立进程组并清理仍存活的后代."""
    process = MagicMock(pid=4321)
    kill_group = MagicMock()
    monkeypatch.setitem(vars(run_module.sys), "platform", "linux")
    monkeypatch.setitem(vars(run_module.os), "killpg", kill_group)
    monkeypatch.setitem(vars(run_module.signal), "SIGKILL", 9)

    assert STOP_CONSOLE_PROCESS(process) is True
    assert kill_group.call_args_list[0].args == (4321, run_module.signal.SIGTERM)
    assert kill_group.call_args_list[1].args == (4321, 9)
    process.wait.assert_called_once_with(timeout=10)


def test_console_run_rejects_invalid_port() -> None:
    """测试控制台命令拒绝非法端口."""
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
    assert "--port 必须在 1 到 65535 之间" in unstyle(result.output)


def test_console_run_rejects_startup_timeout(
        monkeypatch: pytest.MonkeyPatch,
        mock_console_stop: MagicMock,
) -> None:
    """测试服务未就绪时不显示就绪状态."""
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
        "http://127.0.0.1:8701/ready",
        timeout_seconds=120,
    )
    mock_console_stop.assert_called_once_with(process)


def test_console_run_propagates_process_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台命令返回子进程异常退出码."""
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
        mock_console_stop: MagicMock,
) -> None:
    """测试控制台命令收到中断时终止子进程."""
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
    assert "Datamind 管理控制台已停止" in result.output
    mock_console_stop.assert_called_once_with(process)
