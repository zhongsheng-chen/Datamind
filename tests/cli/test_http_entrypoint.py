"""HTTP 子进程入口测试.

验证启动提示过滤保留第三方日志内容和原入口的退出行为。

核心功能：
  - test_startup_hint_filter_only_removes_duplicate_hint:
    验证仅移除重复停止提示，保留启动消息、格式化参数和日志级别
  - test_startup_hint_filter_preserves_other_records:
    验证其他日志记录保持不变
  - test_entrypoint_keeps_bentoml_exit_behavior:
    验证调用 BentoML 原入口并保留退出码
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datamind.cli import http_entrypoint


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING, logging.ERROR])
def test_startup_hint_filter_only_removes_duplicate_hint(level):
    """测试仅移除重复停止提示，保留启动消息、格式化参数和日志级别."""
    message = (
        'Starting production %s BentoServer from "%s" '
        "listening on %s://%s:%d (Press CTRL+C to quit)"
    )
    record = logging.LogRecord(
        "bentoml.serve",
        level,
        __file__,
        1,
        message,
        ("HTTP", "datamind.target", "http", "localhost", 8700),
        None,
    )

    assert http_entrypoint.StartupHintFilter().filter(record)
    assert "Press CTRL+C" not in record.getMessage()
    assert "localhost:8700" in record.getMessage()
    assert record.levelno == level
    assert record.args == ("HTTP", "datamind.target", "http", "localhost", 8700)


@pytest.mark.parametrize(
    "name,message",
    [
        ("bentoml.serve", "solver failed (Press CTRL+C to quit)"),
        ("other", "Starting production server (Press CTRL+C to quit)"),
        ("bentoml.serve", "Starting production server without a hint"),
    ],
)
def test_startup_hint_filter_preserves_other_records(name, message):
    """测试非目标日志记录的消息和级别保持不变."""
    record = logging.LogRecord(name, logging.ERROR, __file__, 1, message, (), None)

    assert http_entrypoint.StartupHintFilter().filter(record)
    assert record.msg == message
    assert record.levelno == logging.ERROR


def test_entrypoint_keeps_bentoml_exit_behavior(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试调用 BentoML 原入口并原样传递退出码."""
    logger = MagicMock()
    monkeypatch.setattr(
        "datamind.cli.http_entrypoint.logging",
        SimpleNamespace(getLogger=lambda _name: logger),
    )
    runner = MagicMock(side_effect=SystemExit(7))
    monkeypatch.setattr(
        "datamind.cli.http_entrypoint.runpy",
        SimpleNamespace(run_module=runner),
    )

    with pytest.raises(SystemExit) as error:
        http_entrypoint.main()

    assert error.value.code == 7
    logger.addFilter.assert_called_once()
    runner.assert_called_once_with("bentoml", run_name="__main__")
