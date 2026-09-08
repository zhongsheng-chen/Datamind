"""CLI 测试公共夹具

隔离 CLI 主入口的真实日志输出。

核心功能：
  - isolate_cli_entry_logging:
    为 CLI 测试隔离主入口日志初始化
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import datamind.cli.main as main_module


@pytest.fixture(autouse=True)
def isolate_cli_entry_logging(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """隔离 CLI 主入口日志初始化"""
    logging_config = MagicMock()
    monkeypatch.setitem(
        vars(main_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=logging_config
        ),
    )
    monkeypatch.setitem(
        vars(main_module),
        "setup_logging",
        lambda _config: None,
    )
