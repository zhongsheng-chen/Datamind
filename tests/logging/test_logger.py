# tests/logging/test_logger.py

"""日志获取接口测试

验证 get_logger 对日志名称、默认参数和上下文绑定的处理。

核心功能：
  - test_get_logger_passes_name:
    验证向 structlog 传递指定日志名称
  - test_get_logger_passes_none_by_default:
    验证未指定名称时向 structlog 传递 None
  - test_get_logger_does_not_bind_context:
    验证 get_logger 不额外绑定当前上下文
"""

from typing import Any

import pytest
import structlog

from datamind.logging.logger import get_logger


def test_get_logger_passes_name(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试传递指定日志名称"""
    captured: dict[
        str,
        str | None,
    ] = {}
    expected_logger = object()

    def fake_get_logger(
            name: str | None = None,
    ) -> object:
        captured[
            "name"
        ] = name

        return expected_logger

    monkeypatch.setitem(
        vars(structlog),
        "get_logger",
        fake_get_logger,
    )

    logger = get_logger(
        "datamind.services.catalog"
    )

    assert logger is expected_logger
    assert captured["name"] == "datamind.services.catalog"


def test_get_logger_passes_none_by_default(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未指定名称时传递 None"""
    captured: dict[
        str,
        str | None,
    ] = {}
    expected_logger = object()

    def fake_get_logger(
            name: str | None = None,
    ) -> object:
        captured[
            "name"
        ] = name

        return expected_logger

    monkeypatch.setitem(
        vars(structlog),
        "get_logger",
        fake_get_logger,
    )

    logger = get_logger()

    assert logger is expected_logger
    assert captured["name"] is None


def test_get_logger_does_not_bind_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 get_logger 不额外绑定上下文"""

    class DummyLogger:
        """测试日志实例"""

        def bind(
                self,
                **_kwargs: Any,
        ) -> None:
            """禁止调用 bind"""
            raise AssertionError(
                "get_logger 不应调用 bind()"
            )

    dummy_logger = DummyLogger()

    monkeypatch.setitem(
        vars(structlog),
        "get_logger",
        lambda name=None: dummy_logger,
    )

    logger = get_logger(
        "datamind.test"
    )

    assert logger is dummy_logger
