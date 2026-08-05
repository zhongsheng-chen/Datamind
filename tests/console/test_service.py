# tests/console/test_service.py

"""管理控制台运行服务测试

验证独立 BentoML 控制台服务的初始化行为。

核心功能：
  - test_console_service_initializes_logging: 验证控制台日志初始化
"""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


service_module = importlib.import_module(
    "datamind.console.service"
)


def test_console_service_initializes_logging(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台服务使用统一配置初始化日志"""
    logging_config = MagicMock()
    setup_logging = MagicMock()
    monkeypatch.setitem(
        vars(service_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=logging_config
        ),
    )
    monkeypatch.setitem(
        vars(service_module),
        "setup_logging",
        setup_logging,
    )

    service_module.DatamindConsoleService.inner()

    setup_logging.assert_called_once_with(
        logging_config
    )
