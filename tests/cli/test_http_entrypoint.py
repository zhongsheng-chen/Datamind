"""HTTP 子进程启动提示过滤测试，保持第三方日志及退出行为."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datamind.cli import http_entrypoint


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING, logging.ERROR])
def test_startup_hint_filter_only_removes_duplicate_hint(level):
    """保留第三方启动消息和格式化参数，只去除其重复停止提示."""
    message = 'Starting production %s BentoServer from "%s" listening on %s://%s:%d (Press CTRL+C to quit)'
    record = logging.LogRecord("bentoml.serve", level, __file__, 1, message,
                               ("HTTP", "datamind.target", "http", "localhost", 8700), None)
    assert http_entrypoint.StartupHintFilter().filter(record)
    assert "Press CTRL+C" not in record.getMessage()
    assert "localhost:8700" in record.getMessage()
    assert record.levelno == level
    assert record.args == ("HTTP", "datamind.target", "http", "localhost", 8700)


@pytest.mark.parametrize("name,message", [
    ("bentoml.serve", "solver failed (Press CTRL+C to quit)"),
    ("other", "Starting production server (Press CTRL+C to quit)"),
    ("bentoml.serve", "Starting production server without a hint"),
])
def test_startup_hint_filter_preserves_other_records(name, message):
    """不屏蔽异常、警告或其他组件的消息."""
    record = logging.LogRecord(name, logging.ERROR, __file__, 1, message, (), None)
    assert http_entrypoint.StartupHintFilter().filter(record)
    assert record.msg == message
    assert record.levelno == logging.ERROR


def test_entrypoint_keeps_bentoml_exit_behavior(monkeypatch):
    """仅委托原入口，退出码原样传播，不接管信号或子进程."""
    logger = MagicMock()
    monkeypatch.setattr(http_entrypoint, "logging", SimpleNamespace(getLogger=lambda _name: logger))
    runner = MagicMock(side_effect=SystemExit(7))
    monkeypatch.setattr(http_entrypoint, "runpy", SimpleNamespace(run_module=runner))
    with pytest.raises(SystemExit) as error:
        http_entrypoint.main()
    assert error.value.code == 7
    logger.addFilter.assert_called_once()
    runner.assert_called_once_with("bentoml", run_name="__main__")
