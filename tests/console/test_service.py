"""管理控制台运行服务测试

验证独立 BentoML 控制台服务的初始化行为。

核心功能：
  - test_console_service_initializes_logging:
    验证控制台日志初始化
"""

import importlib
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
    monkeypatch.setenv("DATAMIND_SERVICE_INSTANCE_ID", "console-test")
    worker_logger = MagicMock()
    worker_logger.bind.return_value = worker_logger
    monkeypatch.setitem(
        vars(service_module.structlog),
        "get_logger",
        lambda _name: worker_logger,
    )
    setup_logging = MagicMock()
    monkeypatch.setitem(
        vars(service_module),
        "get_logging_config",
        lambda: logging_config,
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
    worker_logger.bind.assert_any_call(service_instance_id="console-test")
    worker_logger.bind.assert_any_call(pid=service_module.os.getpid())
    worker_logger.info.assert_called_once_with("管理控制台 Worker 初始化完成")
