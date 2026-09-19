"""日志系统初始化

配置 structlog 处理器链，支持 JSON、文本输出以及同步、异步日志。

核心功能：
  - setup_logging: 初始化日志系统
  - shutdown_logging: 关闭日志系统并释放日志资源

使用示例：
  from datamind.config import get_settings
  from datamind.logging import (
      setup_logging,
      shutdown_logging,
  )

  settings = get_settings()
  setup_logging(settings.logging)

  # 进程退出前可显式调用
  shutdown_logging()
"""

import logging
from contextlib import suppress
from logging.handlers import QueueListener

import structlog
from structlog.typing import Processor

from datamind.config.logging import LoggingConfig
from datamind.logging.handlers import (
    create_async_handler,
    create_console_handler,
    create_file_handler,
)
from datamind.logging.processors import (
    add_context,
    add_timestamp,
    mask_sensitive,
    sampling,
)
from datamind.logging.render import (
    json_renderer,
    text_renderer,
)


_LOG_LISTENER: QueueListener | None = None
_LOG_HANDLERS: list[logging.Handler] = []
_ROOT_HANDLERS: list[logging.Handler] = []


def _logger_factory(
        name: str | None = None,
) -> logging.Logger:
    """创建标准库日志实例

    参数：
        name: 日志名称，未提供时使用 datamind

    返回：
        logging.Logger 实例
    """
    return logging.getLogger(name or "datamind")


def _safe_flush_and_close(
        handler: logging.Handler,
) -> None:
    """安全刷新并关闭日志 handler

    参数：
        handler: 待刷新和关闭的日志 handler
    """
    with suppress(
        OSError,
        RuntimeError,
        ValueError,
    ):
        handler.flush()

    with suppress(
        OSError,
        RuntimeError,
        ValueError,
    ):
        handler.close()


def shutdown_logging() -> None:
    """关闭日志系统

    停止异步日志监听器，刷新并关闭已创建的 handler，
    同时清空 datamind logger，避免重复初始化时重复输出。
    """
    global _LOG_LISTENER
    global _LOG_HANDLERS
    global _ROOT_HANDLERS

    datamind_logger = logging.getLogger("datamind")
    root_logger = logging.getLogger()

    if _LOG_LISTENER is not None:
        try:
            _LOG_LISTENER.stop()

        finally:
            _LOG_LISTENER = None

    handlers = list(datamind_logger.handlers)

    for handler in _ROOT_HANDLERS:
        if handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    for handler in _LOG_HANDLERS:
        if handler not in handlers:
            handlers.append(handler)

    for handler in handlers:
        _safe_flush_and_close(handler)

    datamind_logger.handlers = []
    _LOG_HANDLERS = []
    _ROOT_HANDLERS = []


def setup_logging(
        config: LoggingConfig,
) -> None:
    """初始化日志系统

    参数：
        config: 日志配置对象
    """
    global _LOG_LISTENER
    global _LOG_HANDLERS
    global _ROOT_HANDLERS

    shutdown_logging()

    if config.enable_file:
        config.dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
    ]

    if config.sample_rate < 1.0:
        processors.append(
            sampling(config.sample_rate)
        )

    processors.extend(
        [
            add_timestamp(
                config.timezone,
                config.date_format,
            ),
            add_context(),
        ]
    )

    if config.mask_sensitive:
        processors.append(
            mask_sensitive(
                mask_char=config.mask_char,
                prefix=config.unmasked_prefix,
                suffix=config.unmasked_suffix,
            )
        )

    processors.append(
        structlog.processors.format_exc_info
    )

    renderer = (
        json_renderer()
        if str(config.format) == "json"
        else text_renderer()
    )
    level = getattr(
        logging,
        str(config.level).upper(),
    )

    structlog.configure(
        processors=[
            *processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            level
        ),
        context_class=dict,
        logger_factory=_logger_factory,
        cache_logger_on_first_use=False,
    )

    # 第三方 LogRecord 已完成级别过滤，跳过首个 filter_by_level。
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=processors[1:],
    )

    output_handlers: list[logging.Handler] = []

    if config.enable_console:
        console_handler = create_console_handler(
            formatter
        )
        console_handler.setLevel(
            getattr(
                logging,
                str(config.console_level).upper(),
            )
        )
        output_handlers.append(
            console_handler
        )

    if config.enable_file:
        file_handler = create_file_handler(config)
        file_handler.setFormatter(formatter)
        output_handlers.append(file_handler)
    else:
        file_handler = None

    datamind_logger = logging.getLogger("datamind")
    datamind_logger.setLevel(level)
    datamind_logger.propagate = False

    # 第三方服务日志经 root 写入文件，避免重复输出到控制台。
    if file_handler is not None:
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        _ROOT_HANDLERS = [file_handler]

    else:
        _ROOT_HANDLERS = []

    if config.enable_async and output_handlers:
        queue_handler, listener = create_async_handler(
            output_handlers
        )
        listener.start()

        _LOG_LISTENER = listener
        _LOG_HANDLERS = [
            queue_handler,
            *output_handlers,
        ]
        datamind_logger.handlers = [
            queue_handler,
        ]

    else:
        _LOG_LISTENER = None
        _LOG_HANDLERS = output_handlers.copy()
        datamind_logger.handlers = output_handlers
