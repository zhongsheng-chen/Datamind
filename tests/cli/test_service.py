"""模型服务 CLI 测试.

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
    monkeypatch.setattr(
        type(run_module.console),
        "is_terminal",
        property(lambda _console: interactive),
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
    process.poll.return_value = None
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
    assert result.output.count("服务已就绪") == 1
    assert result.output.count("正在启动服务，等待 Worker 就绪") == 1
    assert ("按 Ctrl+C 停止。" in result.output) is interactive
    assert "Press Ctrl+C to stop" not in result.output
    assert result.output.index("Datamind") < result.output.index("正在启动服务")
    assert result.output.index("正在启动服务") < result.output.index("服务已就绪")
    assert result.output.count("Powered by") == 1
    command = popen.call_args.args[0]
    assert ("--reload" in command) is reload_enabled
    assert "--quiet" in command
    startup_events = [
        call
        for call in structured_logger.info.call_args_list
        if call.args == ("正在启动服务，等待 Worker 就绪",)
    ]
    assert len(startup_events) == 1
    completed_events = [
        call.kwargs
        for call in structured_logger.info.call_args_list
        if call.args == ("服务已就绪",)
    ]
    assert len(completed_events) == 1
    assert completed_events[0]["workers"] == 1
    assert completed_events[0]["startup_seconds"] >= 0
    startup_details = [
        call.kwargs
        for call in structured_logger.debug.call_args_list
        if call.args == ("Datamind 服务启动完成",)
    ]
    assert startup_details[0]["pid"] == 12345
    assert startup_details[0]["service_instance_id"] == (
        popen.call_args.kwargs["env"]["DATAMIND_SERVICE_INSTANCE_ID"]
    )
