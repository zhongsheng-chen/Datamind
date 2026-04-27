# datamind/logging/setup.py

"""日志系统初始化

配置 structlog 处理器链，支持 JSON 文本两种输出格式，同时支持同步异步日志。

核心功能：
  - setup_logging: 初始化日志系统（处理器链、渲染器、handler）

使用示例：
  from datamind.logging import setup_logging
  from datamind.config import get_settings

  settings = get_settings()
  setup_logging(settings.logging)
"""

import logging
import structlog

from datamind.config.logging import LoggingConfig
from datamind.logging.processors import (
    add_timestamp,
    add_context,
    mask_sensitive,
    sampling,
)
from datamind.logging.render import text_renderer, json_renderer
from datamind.logging.handlers import (
    create_file_handler,
    create_console_handler,
    create_async_handler,
)


def _logger_factory(name=None):
    """统一日志工厂

    structlog 可能传入 logger name，但本系统不做 routing，
    所有日志统一进入 datamind logger。

    参数：
        name: 日志名称（忽略）

    返回：
        logging.Logger 实例
    """
    _ = name
    return logging.getLogger("datamind")


def setup_logging(config: LoggingConfig) -> None:
    """初始化日志系统

    参数：
        config: 日志配置对象
    """
    if config.enable_file:
        config.dir.mkdir(parents=True, exist_ok=True)

    # 构建处理器链
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_timestamp(config.timezone, config.date_format),
        add_context(),
    ]

    if config.mask_sensitive:
        processors.append(
            mask_sensitive(
                mask_char=config.mask_char,
                prefix=config.unmasked_prefix,
                suffix=config.unmasked_suffix,
            )
        )

    if config.sample_rate < 1.0:
        processors.append(sampling(config.sample_rate))

    processors.append(structlog.processors.format_exc_info)

    # 选择渲染器
    if config.format == "json":
        renderer = json_renderer()
    else:
        renderer = text_renderer()

    # 配置 structlog
    structlog.configure(
        processors=processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, config.level.upper())
        ),
        context_class=dict,
        logger_factory=_logger_factory,
        cache_logger_on_first_use=True,
    )

    # 构建格式化器
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=processors,
    )

    # 构建处理器
    handlers = []

    if config.enable_console:
        handlers.append(create_console_handler(formatter))

    if config.enable_file:
        file_handler = create_file_handler(config)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # 配置日志器
    datamind_logger = logging.getLogger("datamind")
    datamind_logger.setLevel(getattr(logging, config.level.upper()))
    datamind_logger.propagate = False

    # 异步或同步模式
    if config.enable_async:
        queue_handler, listener = create_async_handler(handlers)
        listener.start()
        datamind_logger.handlers = [queue_handler]
    else:
        datamind_logger.handlers = handlers