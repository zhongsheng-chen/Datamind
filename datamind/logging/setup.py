# datamind/logging/setup.py

"""日志系统初始化

配置 structlog 处理器链，支持 JSON 和文本两种输出格式，同时支持同步和异步日志。
控制台输出简洁文本格式，文件输出相同格式（无颜色）。

核心功能：
  - setup_logging: 初始化日志系统（处理器、处理器链、渲染器）

使用示例：
  from datamind.logging import setup_logging
  from datamind.config import get_settings

  settings = get_settings()
  setup_logging(settings.logging)
"""

import logging
import structlog
from queue import Queue
from logging.handlers import (
    QueueHandler,
    QueueListener,
    TimedRotatingFileHandler,
    RotatingFileHandler,
)
from structlog.stdlib import ProcessorFormatter

from datamind.config.logging import LoggingConfig
from datamind.logging.processors import (
    add_timestamp,
    mask_sensitive,
    sampling,
)
from datamind.logging.retention import start_retention_worker


def _create_file_handler(config: LoggingConfig):
    """创建文件处理器

    参数：
        config: 日志配置对象

    返回：
        文件处理器实例
    """
    if config.rotation == "time":
        return TimedRotatingFileHandler(
            filename=config.dir / config.filename,
            when=config.rotation_when,
            interval=config.rotation_interval,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    if config.rotation == "size":
        return RotatingFileHandler(
            filename=config.dir / config.filename,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding=config.encoding,
        )

    raise ValueError(f"不支持的轮转策略: {config.rotation}")


def _console_renderer(_, __, event_dict):
    """
    控制台日志渲染器

    格式：
        time | level | [trace_id] | [request_id] | event | kv

    说明：
        - trace_id / request_id：存在时才输出（key=value）
        - event：主日志内容
        - kv：额外字段（key=value，逗号分隔）
    """
    trace = event_dict.pop("trace_id", None)
    req = event_dict.pop("request_id", None)

    cols = [
        event_dict.pop("timestamp", ""),
        f"{event_dict.pop('level', '').upper():<8}",
    ]

    if trace or req:
        cols.append(f"trace={trace or '-'}")
        cols.append(f"req={req or '-'}")

    cols.append(event_dict.pop("event", ""))

    msg = " | ".join(cols)

    if event_dict:
        msg += " | " + ", ".join(
            f"{k}={v}" for k, v in sorted(event_dict.items())
        )

    return msg


def setup_logging(config: LoggingConfig) -> None:
    """初始化日志系统

    参数：
        config: 日志配置对象
    """
    if config.enable_file:
        config.dir.mkdir(parents=True, exist_ok=True)

    handlers = []

    # 构建共享处理器链
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_timestamp(config.timezone, config.date_format),
    ]

    if config.mask_sensitive:
        shared_processors.append(
            mask_sensitive(
                mask_char=config.mask_char,
                prefix=config.unmasked_prefix,
                suffix=config.unmasked_suffix,
            )
        )

    if config.sample_rate < 1.0:
        shared_processors.append(sampling(config.sample_rate))

    shared_processors.append(structlog.processors.format_exc_info)

    # 选择渲染器
    if config.format == "json":
        console_renderer = structlog.processors.JSONRenderer()
        file_renderer = structlog.processors.JSONRenderer()
    else:
        console_renderer = _console_renderer
        file_renderer = _console_renderer

    # 创建格式化器
    console_formatter = ProcessorFormatter(
        processor=console_renderer,
        foreign_pre_chain=shared_processors,
    )

    file_formatter = ProcessorFormatter(
        processor=file_renderer,
        foreign_pre_chain=shared_processors,
    )

    # 添加控制台处理器
    if config.enable_console:
        console = logging.StreamHandler()
        console.setFormatter(console_formatter)
        handlers.append(console)

    # 添加文件处理器
    if config.enable_file:
        file_handler = _create_file_handler(config)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # 配置根日志器
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.level.upper()))

    # 异步日志包装
    if config.enable_async:
        queue = Queue(-1)
        queue_handler = QueueHandler(queue)
        listener = QueueListener(
            queue,
            *handlers,
            respect_handler_level=True,
        )
        listener.start()
        root.handlers = [queue_handler]
    else:
        root.handlers = handlers

    # 配置主处理器链
    structlog.configure(
        processors=shared_processors + [ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 启动日志保留清理任务
    if config.enable_file and config.retention_days > 0:
        start_retention_worker(config)