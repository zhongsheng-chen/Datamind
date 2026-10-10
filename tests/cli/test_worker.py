"""任务 Worker CLI 测试.

验证配置继承、命令行覆盖和非法参数校验。

核心功能：
  - test_worker_run_uses_config: 验证启动配置与队列参数
  - test_worker_run_rejects_invalid_options: 验证非法参数不会启动 Worker
"""

import importlib
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from datamind.cli.main import app
from datamind.config.worker import TaskWorkerConfig
from datamind.constants import LogLevel
import datamind.runtime.task_queue.entrypoints.worker as process_module


run_module = importlib.import_module("datamind.cli.worker.run")
runner = CliRunner()


@pytest.mark.parametrize(
    ("options", "expected_role", "expected_concurrency"),
    [
        ([], "shadow", 2),
        (["--role", "batch"], "batch", 2),
        (["--concurrency", "4"], "shadow", 4),
        (["--role", "all", "--concurrency", "3"], "all", 3),
    ],
)
def test_worker_run_uses_config(
        monkeypatch: pytest.MonkeyPatch,
        options: list[str],
        expected_role: str,
        expected_concurrency: int,
) -> None:
    """测试 CLI 继承配置，并将参数覆盖传递到实际 Worker 启动入口."""
    config = TaskWorkerConfig(
        name="cli-test",
        role="shadow",
        concurrency=2,
        log_level=LogLevel.WARNING,
    )
    worker_main = MagicMock()
    monkeypatch.setitem(vars(run_module), "get_task_worker_config", lambda: config)
    monkeypatch.setitem(vars(process_module.celery_app), "worker_main", worker_main)

    result = runner.invoke(app, ["worker", "run", *options])

    assert result.exit_code == 0, result.output
    worker_main.assert_called_once()
    arguments = worker_main.call_args.args[0]
    queue_config = process_module.get_task_queue_config()
    expected_queues = {
        "all": f"{queue_config.batch_queue},{queue_config.shadow_queue}",
        "batch": queue_config.batch_queue,
        "shadow": queue_config.shadow_queue,
    }
    assert arguments[arguments.index("--queues") + 1] == expected_queues[expected_role]
    assert arguments[arguments.index("--concurrency") + 1] == str(expected_concurrency)
    assert arguments[arguments.index("--loglevel") + 1] == "WARNING"
    assert arguments[arguments.index("--hostname") + 1].startswith("cli-test-")
    assert config.role == "shadow"
    assert config.concurrency == 2


@pytest.mark.parametrize(
    "options",
    [
        ["--role", "invalid"],
        ["--concurrency", "0"],
        ["--concurrency", "-1"],
    ],
)
def test_worker_run_rejects_invalid_options(
        monkeypatch: pytest.MonkeyPatch,
        options: list[str],
) -> None:
    """测试非法角色和并发参数在启动 Worker 前被拒绝."""
    worker_main = MagicMock()
    monkeypatch.setitem(vars(process_module.celery_app), "worker_main", worker_main)

    result = runner.invoke(app, ["worker", "run", *options])

    assert result.exit_code == 2
    worker_main.assert_not_called()
