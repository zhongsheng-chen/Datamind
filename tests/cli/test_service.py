"""模型服务 CLI 测试.

验证模型服务进程启动不依赖本地 CLI 登录会话。

核心功能：
  - test_service_run_does_not_authenticate_cli_user:
    验证服务启动不执行用户认证
  - test_service_ctrl_c_stops_owned_tree:
    验证启动中和就绪后 Ctrl+C 均只清理本次服务进程树
  - test_process_exit_wait_remains_interruptible:
    验证等待子进程时持续检查停止请求
  - test_windows_stop_cleans_process_tree:
    验证 Windows 进程树清理、已退出竞争和真实失败
  - test_posix_stop_escalates_after_timeout:
    验证 POSIX 先终止进程组，超时后强制退出
  - test_worker_shutdown_waits_for_every_acknowledgement:
    验证等待所有 Worker 完成关闭
  - test_worker_shutdown_timeout_is_bounded:
    验证关闭等待具有超时限制
  - test_windows_stop_requests_worker_cleanup_before_tree_termination:
    验证先正常关闭 Worker，再清理监督进程
  - test_replacement_worker_cannot_acknowledge_failed_cleanup:
    验证新 Worker 的回报不能替代原 Worker 的关闭结果
"""

from pathlib import Path
from types import SimpleNamespace
import asyncio
import signal
import subprocess

from unittest.mock import (
    AsyncMock,
    MagicMock,
)
import importlib

import pytest
from typer.testing import CliRunner

import datamind.cli.common as common_module
from datamind.cli.main import app
from datamind.constants import Environment


run_module = importlib.import_module(
    "datamind.cli.service.run"
)
runner = CliRunner()


@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize("console_logs_info", [False, True])
@pytest.mark.parametrize(
    ("environment", "arguments", "reload_enabled"),
    [
        ("development", [], False),
        ("development", ["--reload"], True),
        ("production", [], False),
        ("production", ["--reload"], True),
    ],
)
def test_service_run_does_not_authenticate_cli_user(
        monkeypatch: pytest.MonkeyPatch,
        environment: str,
        arguments: list[str],
        reload_enabled: bool,
        interactive: bool,
        console_logs_info: bool,
) -> None:
    """测试服务启动不执行用户认证."""
    monkeypatch.setitem(
        vars(run_module.console),
        "_force_terminal",
        interactive,
    )
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
    process.poll.return_value = 0
    popen = MagicMock(
        return_value=process
    )
    structured_logger = MagicMock()
    if console_logs_info:
        structured_logger.info.side_effect = (
            lambda message, **_fields: run_module.console.info(message)
        )
    monkeypatch.setitem(vars(run_module), "logger", structured_logger)

    settings = SimpleNamespace(
        logging=SimpleNamespace(
            enable_console=console_logs_info,
            level="INFO",
            console_level="INFO",
        ),
        common=SimpleNamespace(environment=Environment(environment)),
        service=SimpleNamespace(
            name="datamind",
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
        lambda _service_id: (
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
            *arguments,
        ],
    )

    assert result.exit_code == 0
    assert "认证失败" not in result.output
    assert "NAME" not in result.output
    assert "ENVIRONMENT" in result.output
    assert environment in result.output
    assert "BIND" in result.output
    assert "127.0.0.1:8700" in result.output
    assert "URL" in result.output
    assert "http://127.0.0.1:8700" in result.output
    assert "WORKERS" in result.output
    assert "RELOAD" in result.output
    assert ("enabled" if reload_enabled else "disabled") in result.output
    assert result.output.count("运行时服务已就绪") == int(console_logs_info)
    assert result.output.count("正在启动运行时服务，等待 Worker 就绪") == int(console_logs_info)
    assert result.output.count("按 Ctrl+C 停止服务") == int(interactive)
    assert "Press Ctrl+C to stop" not in result.output
    if console_logs_info:
        assert result.output.index("Datamind") < result.output.index("正在启动运行时服务")
        assert result.output.index("正在启动运行时服务") < result.output.index("运行时服务已就绪")
    assert result.output.count("Powered by") == 1
    command = popen.call_args.args[0]
    assert command[:3] == [run_module.sys.executable, "-m", "datamind.cli.http_entrypoint"]
    assert ("--reload" in command) is reload_enabled
    assert "--quiet" in command
    startup_events = [
        call
        for call in structured_logger.info.call_args_list
        if call.args == ("正在启动运行时服务，等待 Worker 就绪",)
    ]
    assert len(startup_events) == 1
    completed_events = [
        call.kwargs
        for call in structured_logger.info.call_args_list
        if call.args == ("运行时服务已就绪",)
    ]
    assert len(completed_events) == 1
    assert completed_events[0]["workers"] == 1
    assert completed_events[0]["startup_seconds"] >= 0
    startup_details = [
        call.kwargs
        for call in structured_logger.debug.call_args_list
        if call.args == ("运行时服务启动完成",)
    ]
    assert startup_details[0]["pid"] == 12345
    assert startup_details[0]["service_id"] == (
        popen.call_args.kwargs["env"]["DATAMIND_SERVICE_ID"]
    )


@pytest.mark.parametrize("stage", ["startup", "running"])
def test_service_ctrl_c_stops_owned_tree(
        monkeypatch: pytest.MonkeyPatch,
        stage: str,
) -> None:
    """验证 Ctrl+C 不产生 Abort，且启动中和运行中都清理进程树."""
    settings = SimpleNamespace(
        logging=SimpleNamespace(),
        common=SimpleNamespace(environment=Environment.DEVELOPMENT),
        service=SimpleNamespace(name="datamind", host="127.0.0.1", port=8700, workers=1),
    )
    process = MagicMock(pid=12345)
    process.poll.return_value = None
    cleanup = MagicMock(return_value=0)
    structured_logger = MagicMock()
    monkeypatch.setitem(vars(run_module), "get_settings", lambda: settings)
    monkeypatch.setitem(vars(run_module), "setup_logging", lambda _: None)
    monkeypatch.setitem(vars(run_module), "shutdown_logging", lambda: None)
    monkeypatch.setitem(vars(run_module), "logger", structured_logger)
    monkeypatch.setitem(vars(run_module.subprocess), "Popen", MagicMock(return_value=process))
    monkeypatch.setitem(vars(run_module), "_prepare_ready_dir", lambda _: None)
    monkeypatch.setitem(vars(run_module), "_cleanup_ready_dir", lambda _: None)
    monkeypatch.setitem(vars(run_module), "_stop_service_process", cleanup)
    original_handler = signal.getsignal(signal.SIGINT)

    async def ready(**kwargs):
        if stage == "startup":
            handler = signal.getsignal(signal.SIGINT)
            assert callable(handler)
            handler(signal.SIGINT, None)
            assert kwargs["should_stop"]()
            raise asyncio.CancelledError
        return {"worker"}

    async def wait(_process, should_stop):
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)
        assert should_stop()
        return None

    monkeypatch.setitem(vars(run_module), "_wait_for_workers_ready", ready)
    monkeypatch.setitem(vars(run_module), "_wait_for_process_exit", wait)
    result = runner.invoke(app, ["service", "run"])
    assert result.exit_code == 0, result.output
    assert "Aborted!" not in result.output
    cleanup.assert_called_once()
    assert cleanup.call_args.args == (process,)
    assert cleanup.call_args.kwargs["expected_workers"] == 1
    process.terminate.assert_not_called()
    assert signal.getsignal(signal.SIGINT) is original_handler
    stopped = [call for call in structured_logger.info.call_args_list if call.args == ("运行时服务已停止",)]
    assert len(stopped) == 1
    assert stopped[0].kwargs["stop_reason"] == (
        "startup_interrupted" if stage == "startup" else "keyboard_interrupt"
    )


@pytest.mark.asyncio
async def test_process_exit_wait_remains_interruptible() -> None:
    """验证没有无限期阻塞等待，停止请求无需终端输入即可被处理."""
    process = MagicMock()
    process.poll.return_value = None
    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.02, stop.set)
    result = await asyncio.wait_for(
        run_module._wait_for_process_exit(process, stop.is_set),
        timeout=1,
    )
    assert result is None
    process.wait.assert_not_called()
    process.poll.return_value = 7
    assert await run_module._wait_for_process_exit(process, lambda: False) == 7


@pytest.mark.parametrize("outcome", ["success", "already_exited", "failed"])
def test_windows_stop_cleans_process_tree(
        monkeypatch: pytest.MonkeyPatch,
        outcome: str,
) -> None:
    """验证 taskkill 精确清理拥有的进程树，只有已退出竞争被忽略."""
    monkeypatch.setitem(vars(run_module.sys), "platform", "win32")
    monkeypatch.setitem(vars(subprocess), "CREATE_NO_WINDOW", 0x08000000)
    process = MagicMock(pid=12345)
    process.poll.return_value = 0 if outcome == "already_exited" else None
    process.wait.return_value = 0
    stop = MagicMock()
    if outcome != "success":
        stop.side_effect = subprocess.CalledProcessError(128, "taskkill")
    monkeypatch.setitem(vars(run_module.subprocess), "run", stop)
    if outcome == "failed":
        with pytest.raises(subprocess.CalledProcessError):
            run_module._stop_service_process(process)
    else:
        assert run_module._stop_service_process(process) == 0
        process.wait.assert_called_once_with(timeout=10)
    assert stop.call_args.args[0] == ["taskkill", "/PID", "12345", "/T", "/F"]
    assert stop.call_args.kwargs["timeout"] == 10


def test_posix_stop_escalates_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证进程组先收到 SIGTERM，超时后收到 SIGKILL，等待始终有界."""
    monkeypatch.setitem(vars(run_module.sys), "platform", "linux")
    monkeypatch.setitem(vars(signal), "SIGKILL", 9)
    kill = MagicMock()
    monkeypatch.setitem(vars(run_module.os), "killpg", kill)
    process = MagicMock(pid=12345)
    process.wait.side_effect = [subprocess.TimeoutExpired("service", 10), -9]
    assert run_module._stop_service_process(process) == -9
    assert [call.args for call in kill.call_args_list] == [
        (12345, signal.SIGTERM), (12345, signal.SIGKILL),
    ]
    assert all(call.kwargs == {"timeout": 10} for call in process.wait.call_args_list)


def test_worker_shutdown_waits_for_every_acknowledgement(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证已关闭 Worker 数量不足时继续等待，停止请求先于回报写入."""
    process = MagicMock()
    process.poll.return_value = None
    sleeps = []

    def acknowledge(_seconds):
        assert (tmp_path / "stop.request").exists()
        sleeps.append(_seconds)
        (tmp_path / f"worker_{len(sleeps)}.stopped").touch()

    monkeypatch.setitem(vars(run_module), "time", SimpleNamespace(monotonic=lambda: 0.0, sleep=acknowledge))
    assert run_module._wait_for_worker_shutdown(process, tmp_path, 2)
    assert len(sleeps) == 2


def test_worker_shutdown_timeout_is_bounded(tmp_path: Path) -> None:
    """验证 Worker 未完成清理时可在超时后执行强制兜底."""
    process = MagicMock()
    process.poll.return_value = None
    assert not run_module._wait_for_worker_shutdown(process, tmp_path, 1, timeout_seconds=0)
    assert (tmp_path / "stop.request").exists()


@pytest.mark.parametrize("complete", [True, False])
def test_windows_stop_requests_worker_cleanup_before_tree_termination(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        complete: bool,
) -> None:
    """验证先等关闭钩子，之后清理监督进程，超时有明确告警."""
    monkeypatch.setitem(vars(run_module.sys), "platform", "win32")
    monkeypatch.setitem(vars(subprocess), "CREATE_NO_WINDOW", 0x08000000)
    process = MagicMock(pid=12345)
    process.poll.return_value = None
    process.wait.return_value = 0
    events = []
    graceful = MagicMock(side_effect=lambda *args: events.append("workers") or complete)
    terminate = MagicMock(side_effect=lambda *args, **kwargs: events.append("supervisor"))
    structured_logger = MagicMock()
    monkeypatch.setitem(vars(run_module), "_wait_for_worker_shutdown", graceful)
    monkeypatch.setitem(vars(run_module.subprocess), "run", terminate)
    monkeypatch.setitem(vars(run_module), "logger", structured_logger)
    assert run_module._stop_service_process(process, ready_dir=tmp_path, expected_workers=4) == 0
    assert events == ["workers", "supervisor"]
    graceful.assert_called_once_with(process, tmp_path, 4)
    assert structured_logger.warning.call_count == int(not complete)



def test_replacement_worker_cannot_acknowledge_failed_cleanup(
        tmp_path: Path,
) -> None:
    """验证重启 Worker 的回报不能替代原 Worker 的卸载结果."""
    (tmp_path / "original_worker.json").write_text("{}")
    (tmp_path / "replacement_worker.stopped").touch()
    process = MagicMock()
    process.poll.return_value = None
    assert not run_module._wait_for_worker_shutdown(process, tmp_path, 1, timeout_seconds=0)
