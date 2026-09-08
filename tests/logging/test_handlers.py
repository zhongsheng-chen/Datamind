"""日志输出通道处理器测试

验证文件、控制台和异步日志 handler 的创建与分发行为。

核心功能：
  - test_create_time_rotating_file_handler:
    验证创建按时间轮转的文件日志 handler
  - test_create_size_rotating_file_handler:
    验证创建按大小轮转的文件日志 handler
  - test_file_handlers_coordinate_shared_log_rotation:
    验证多个文件日志 handler 协调同一日志文件轮转
  - test_create_file_handler_rejects_unknown_rotation:
    验证拒绝未知日志轮转策略
  - test_create_console_handler:
    验证创建控制台日志 handler
  - test_create_async_handler:
    验证创建异步队列日志 handler
  - test_async_handler_dispatches_log_record:
    验证异步日志 handler 将日志记录交给输出 handler
"""

import logging
import sys
from logging.handlers import (
    QueueHandler,
    QueueListener,
)
from pathlib import Path

import pytest
from concurrent_log_handler import (
    ConcurrentRotatingFileHandler,
    ConcurrentTimedRotatingFileHandler,
)

from datamind.config.logging import LoggingConfig
from datamind.constants import (
    RotationType,
    RotationWhen,
)
from datamind.logging.handlers import (
    create_async_handler,
    create_console_handler,
    create_file_handler,
)


def create_config(
        tmp_path: Path,
        **overrides: object,
) -> LoggingConfig:
    """创建不读取外部配置源的日志配置"""
    config_kwargs: dict[str, object] = {
        "dir": tmp_path / "logs",
        "filename": "datamind.log",
        "rotation": RotationType.TIME,
        "rotation_when": RotationWhen.MIDNIGHT,
        "rotation_interval": 1,
        "max_bytes": 1024,
        "backup_count": 3,
        "encoding": "utf-8",
    }
    config_kwargs.update(
        overrides
    )

    return LoggingConfig.model_construct(
        **config_kwargs
    )


def test_create_time_rotating_file_handler(
        tmp_path: Path,
) -> None:
    """测试创建按时间轮转的文件日志 handler"""
    config = create_config(
        tmp_path,
        rotation=RotationType.TIME,
        rotation_when=RotationWhen.MIDNIGHT,
    )

    handler = create_file_handler(
        config
    )

    try:
        assert isinstance(
            handler,
            ConcurrentTimedRotatingFileHandler,
        )
        assert Path(handler.baseFilename) == (
            config.dir / config.filename
        ).resolve()
        assert handler.backupCount == config.backup_count
        assert config.dir.exists()

    finally:
        handler.close()


def test_create_size_rotating_file_handler(
        tmp_path: Path,
) -> None:
    """测试创建按大小轮转的文件日志 handler"""
    config = create_config(
        tmp_path,
        rotation=RotationType.SIZE,
        max_bytes=2048,
        backup_count=5,
    )

    handler = create_file_handler(
        config
    )

    try:
        assert isinstance(
            handler,
            ConcurrentRotatingFileHandler,
        )
        assert handler.maxBytes == 2048
        assert handler.backupCount == 5
        assert Path(handler.baseFilename) == (
            config.dir / config.filename
        ).resolve()

    finally:
        handler.close()


def test_file_handlers_coordinate_shared_log_rotation(
        tmp_path: Path,
) -> None:
    """测试多个 handler 协调同一日志文件轮转"""
    config = create_config(
        tmp_path,
        rotation=RotationType.SIZE,
        max_bytes=1,
        backup_count=3,
    )
    first_handler = create_file_handler(
        config
    )
    second_handler = create_file_handler(
        config
    )
    formatter = logging.Formatter(
        "%(message)s"
    )
    first_handler.setFormatter(
        formatter
    )
    second_handler.setFormatter(
        formatter
    )

    try:
        first_handler.emit(
            logging.makeLogRecord({
                "msg": "first",
                "levelno": logging.INFO,
                "levelname": "INFO",
            })
        )
        second_handler.emit(
            logging.makeLogRecord({
                "msg": "second",
                "levelno": logging.INFO,
                "levelname": "INFO",
            })
        )

    finally:
        first_handler.close()
        second_handler.close()

    assert (
        config.dir / config.filename
    ).exists()
    assert (
        config.dir / f"{config.filename}.1"
    ).exists()


def test_create_file_handler_rejects_unknown_rotation(
        tmp_path: Path,
) -> None:
    """测试拒绝未知日志轮转策略"""
    config = create_config(
        tmp_path,
        rotation="unknown",
    )

    with pytest.raises(
            ValueError,
            match="不支持的日志轮转策略",
    ):
        create_file_handler(
            config
        )


def test_create_console_handler() -> None:
    """测试创建控制台日志 handler"""
    formatter = logging.Formatter(
        "%(levelname)s | %(message)s"
    )

    handler = create_console_handler(
        formatter
    )

    try:
        assert isinstance(
            handler,
            logging.StreamHandler,
        )
        assert handler.stream is sys.stdout
        assert handler.formatter is formatter

    finally:
        handler.close()


def test_create_async_handler() -> None:
    """测试创建异步队列日志 handler"""
    output_handler = logging.NullHandler()

    queue_handler, listener = create_async_handler(
        [
            output_handler,
        ]
    )

    try:
        assert isinstance(
            queue_handler,
            QueueHandler,
        )
        assert isinstance(
            listener,
            QueueListener,
        )
        assert listener.handlers == (
            output_handler,
        )
        assert listener.respect_handler_level is True

    finally:
        output_handler.close()


def test_async_handler_dispatches_log_record() -> None:
    """测试异步日志 handler 将日志记录交给输出 handler"""

    class CollectingHandler(logging.Handler):
        """收集日志记录的测试 handler"""

        def __init__(self) -> None:
            super().__init__()
            self.records: list[logging.LogRecord] = []

        def emit(
                self,
                record: logging.LogRecord,
        ) -> None:
            """保存日志记录"""
            self.records.append(
                record
            )

    output_handler = CollectingHandler()
    queue_handler, listener = create_async_handler(
        [
            output_handler,
        ]
    )

    listener.start()

    try:
        log_record = logging.LogRecord(
            name="datamind.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="异步日志测试",
            args=(),
            exc_info=None,
        )

        queue_handler.handle(
            log_record
        )

    finally:
        listener.stop()
        output_handler.close()

    assert len(output_handler.records) == 1
    assert output_handler.records[0].getMessage() == "异步日志测试"
