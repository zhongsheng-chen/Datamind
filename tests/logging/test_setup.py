# tests/logging/test_setup.py

"""日志系统初始化测试

验证日志系统的同步、异步、静默、处理器选择、
重复初始化和资源清理行为。

核心功能：
  - test_logger_factory_uses_default_name:
    验证日志工厂默认使用 datamind 名称
  - test_logger_factory_preserves_explicit_name:
    验证日志工厂保留指定名称
  - test_setup_logging_creates_sync_console_handler:
    验证创建同步控制台日志 handler
  - test_setup_logging_creates_sync_file_handler:
    验证创建同步文件日志 handler
  - test_setup_logging_creates_async_queue_handler:
    验证创建异步队列日志 handler
  - test_setup_logging_allows_silent_mode:
    验证关闭全部输出通道时允许静默运行
  - test_setup_logging_closes_previous_handlers:
    验证重复初始化时关闭旧 handler
  - test_setup_logging_selects_renderer:
    验证根据日志格式选择对应渲染器
  - test_setup_logging_adds_sampling_and_masking_processors:
    验证按配置加入采样和脱敏处理器
  - test_shutdown_logging_clears_global_state:
    验证关闭日志系统后清理全局状态
"""

import logging
from collections.abc import (
    Callable,
    Iterator,
)
from logging.handlers import QueueHandler
from pathlib import Path
from typing import Any

import pytest
import structlog
from structlog.typing import (
    EventDict,
    Processor,
    WrappedLogger,
)

from datamind.config.logging import LoggingConfig
from datamind.constants import (
    LogFormat,
    LogLevel,
    RotationType,
    RotationWhen,
)
from datamind.logging import setup as logging_setup


def create_config(
        tmp_path: Path,
        **overrides: object,
) -> LoggingConfig:
    """创建不读取外部配置源的日志配置"""
    config_kwargs: dict[str, object] = {
        "level": LogLevel.INFO,
        "format": LogFormat.JSON,
        "encoding": "utf-8",
        "dir": tmp_path / "logs",
        "filename": "datamind.log",
        "date_format": None,
        "timezone": "Asia/Shanghai",
        "rotation": RotationType.TIME,
        "rotation_when": RotationWhen.MIDNIGHT,
        "rotation_interval": 1,
        "max_bytes": 1024,
        "backup_count": 3,
        "retention_days": 7,
        "enable_console": True,
        "enable_file": False,
        "enable_async": False,
        "sample_rate": 1.0,
        "mask_sensitive": True,
        "mask_char": "*",
        "unmasked_prefix": 2,
        "unmasked_suffix": 2,
    }
    config_kwargs.update(
        overrides
    )

    return LoggingConfig.model_construct(
        **config_kwargs
    )


def create_identity_processor() -> Processor:
    """创建原样返回事件字典的测试处理器"""

    def processor(
            _logger: WrappedLogger,
            _method_name: str,
            event_dict: EventDict,
    ) -> EventDict:
        return event_dict

    return processor


def create_renderer_spies(
        calls: list[str],
) -> tuple[
    Callable[[], Processor],
    Callable[[], Processor],
]:
    """创建记录渲染器选择结果的测试桩"""
    renderer = create_identity_processor()

    def fake_json_renderer() -> Processor:
        calls.append("json")

        return renderer

    def fake_text_renderer() -> Processor:
        calls.append("text")

        return renderer

    return (
        fake_json_renderer,
        fake_text_renderer,
    )


@pytest.fixture(autouse=True)
def reset_logging_state() -> Iterator[None]:
    """在每个测试前后清理日志系统"""
    logging_setup.shutdown_logging()

    yield

    logging_setup.shutdown_logging()


def test_logger_factory_uses_default_name() -> None:
    """测试日志工厂默认使用 datamind 名称"""
    logger = logging_setup._logger_factory()

    assert logger is logging.getLogger("datamind")


def test_logger_factory_preserves_explicit_name() -> None:
    """测试日志工厂保留指定名称"""
    logger = logging_setup._logger_factory(
        "datamind.services.catalog"
    )

    assert logger is logging.getLogger(
        "datamind.services.catalog"
    )


def test_setup_logging_creates_sync_console_handler(
        tmp_path: Path,
) -> None:
    """测试同步控制台日志初始化"""
    config = create_config(
        tmp_path,
        enable_console=True,
        enable_file=False,
        enable_async=False,
    )

    logging_setup.setup_logging(config)

    logger = logging.getLogger("datamind")

    assert len(logger.handlers) == 1
    assert isinstance(
        logger.handlers[0],
        logging.StreamHandler,
    )
    assert not isinstance(
        logger.handlers[0],
        QueueHandler,
    )
    assert logger.handlers[0].formatter is not None
    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert logging_setup._LOG_LISTENER is None
    assert logging_setup._LOG_HANDLERS == logger.handlers


def test_setup_logging_creates_sync_file_handler(
        tmp_path: Path,
) -> None:
    """测试同步文件日志初始化"""
    config = create_config(
        tmp_path,
        enable_console=False,
        enable_file=True,
        enable_async=False,
    )

    logging_setup.setup_logging(config)

    logger = logging.getLogger("datamind")

    assert config.dir.exists()
    assert len(logger.handlers) == 1
    assert logger.handlers[0].formatter is not None
    assert logging_setup._LOG_LISTENER is None
    assert logging_setup._LOG_HANDLERS == logger.handlers


def test_setup_logging_creates_async_queue_handler(
        tmp_path: Path,
) -> None:
    """测试异步日志初始化"""
    config = create_config(
        tmp_path,
        enable_console=True,
        enable_file=False,
        enable_async=True,
    )

    logging_setup.setup_logging(config)

    logger = logging.getLogger("datamind")

    assert len(logger.handlers) == 1
    assert isinstance(
        logger.handlers[0],
        QueueHandler,
    )
    assert logging_setup._LOG_LISTENER is not None
    assert len(logging_setup._LOG_HANDLERS) == 2
    assert logging_setup._LOG_HANDLERS[0] is logger.handlers[0]


def test_setup_logging_allows_silent_mode(
        tmp_path: Path,
) -> None:
    """测试控制台和文件均关闭时允许静默运行"""
    config = create_config(
        tmp_path,
        enable_console=False,
        enable_file=False,
        enable_async=True,
    )

    logging_setup.setup_logging(config)

    logger = logging.getLogger("datamind")

    assert logger.handlers == []
    assert logging_setup._LOG_HANDLERS == []
    assert logging_setup._LOG_LISTENER is None


def test_setup_logging_closes_previous_handlers(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试重复初始化时关闭旧 handler"""

    class TrackingHandler(logging.Handler):
        """记录关闭次数的测试 handler"""

        def __init__(self) -> None:
            super().__init__()
            self.close_count = 0

        def emit(
                self,
                record: logging.LogRecord,
        ) -> None:
            """忽略日志记录"""
            _ = record

        def close(self) -> None:
            """记录关闭并执行父类清理"""
            self.close_count += 1
            super().close()

    created_handlers: list[TrackingHandler] = []

    def fake_create_console_handler(
            formatter: logging.Formatter,
    ) -> TrackingHandler:
        handler = TrackingHandler()
        handler.setFormatter(formatter)
        created_handlers.append(handler)

        return handler

    monkeypatch.setitem(
        vars(logging_setup),
        "create_console_handler",
        fake_create_console_handler,
    )

    config = create_config(
        tmp_path,
        enable_console=True,
        enable_file=False,
        enable_async=False,
    )

    logging_setup.setup_logging(config)
    first_handler = created_handlers[0]

    logging_setup.setup_logging(config)
    second_handler = created_handlers[1]

    logger = logging.getLogger("datamind")

    assert first_handler.close_count == 1
    assert second_handler.close_count == 0
    assert logger.handlers == [
        second_handler,
    ]


@pytest.mark.parametrize(
    (
        "log_format",
        "expected_call",
    ),
    [
        (
            LogFormat.JSON,
            "json",
        ),
        (
            LogFormat.TEXT,
            "text",
        ),
    ],
    ids=[
        "json",
        "text",
    ],
)
def test_setup_logging_selects_renderer(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        log_format: LogFormat,
        expected_call: str,
) -> None:
    """测试根据日志格式选择对应渲染器"""
    renderer_calls: list[str] = []
    (
        fake_json_renderer,
        fake_text_renderer,
    ) = create_renderer_spies(
        renderer_calls
    )

    monkeypatch.setitem(
        vars(logging_setup),
        "json_renderer",
        fake_json_renderer,
    )
    monkeypatch.setitem(
        vars(logging_setup),
        "text_renderer",
        fake_text_renderer,
    )

    config = create_config(
        tmp_path,
        format=log_format,
        enable_console=False,
        enable_file=False,
    )

    logging_setup.setup_logging(config)

    assert renderer_calls == [
        expected_call,
    ]


def test_setup_logging_adds_sampling_and_masking_processors(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试按配置加入采样和脱敏处理器"""
    captured: dict[str, Any] = {}
    sampling_rates: list[float] = []
    masking_options: list[tuple[str, int, int]] = []

    sampling_processor = create_identity_processor()
    masking_processor = create_identity_processor()

    def fake_sampling(
            sample_rate: float,
    ) -> Processor:
        sampling_rates.append(sample_rate)

        return sampling_processor

    def fake_mask_sensitive(
            mask_char: str,
            prefix: int,
            suffix: int,
    ) -> Processor:
        masking_options.append(
            (
                mask_char,
                prefix,
                suffix,
            )
        )

        return masking_processor

    def fake_configure(
            **kwargs: Any,
    ) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(
        vars(logging_setup),
        "sampling",
        fake_sampling,
    )
    monkeypatch.setitem(
        vars(logging_setup),
        "mask_sensitive",
        fake_mask_sensitive,
    )
    monkeypatch.setitem(
        vars(structlog),
        "configure",
        fake_configure,
    )

    config = create_config(
        tmp_path,
        sample_rate=0.5,
        mask_sensitive=True,
        mask_char="#",
        unmasked_prefix=1,
        unmasked_suffix=3,
        enable_console=False,
        enable_file=False,
    )

    logging_setup.setup_logging(config)

    processors = captured["processors"]
    assert isinstance(
        processors,
        list,
    )

    assert sampling_rates == [
        0.5,
    ]
    assert masking_options == [
        (
            "#",
            1,
            3,
        ),
    ]
    assert sampling_processor in processors
    assert masking_processor in processors


def test_shutdown_logging_clears_global_state(
        tmp_path: Path,
) -> None:
    """测试关闭日志系统后清理全局状态"""
    config = create_config(
        tmp_path,
        enable_console=True,
        enable_file=False,
        enable_async=True,
    )

    logging_setup.setup_logging(config)
    logging_setup.shutdown_logging()

    logger = logging.getLogger("datamind")

    assert logger.handlers == []
    assert logging_setup._LOG_HANDLERS == []
    assert logging_setup._LOG_LISTENER is None
