## Project Structure
```
    __init__.py
    __pycache__/
    context.py
    logger.py
    processors.py
    retention.py
    setup.py
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\context.py
```python
# datamind/logging/context.py

"""日志上下文

使用 structlog.contextvars 实现请求级别的上下文传递，支持异步和并发场景。

核心功能：
  - set_context: 设置上下文（trace_id / request_id）
  - get_context: 获取当前上下文字典
  - clear_context: 清除上下文
  - request_context: 上下文管理器，用于请求级别的作用域

使用示例：
  from datamind.logging.context import set_context, request_context

  # 全局设置
  set_context(trace_id="trace-123", request_id="req-456")

  # 请求级别作用域
  with request_context(trace_id="trace-789", request_id="req-012"):
      logger.info("处理请求")
"""

from contextlib import contextmanager
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)


def set_context(trace_id: str = None, request_id: str = None) -> None:
    """设置上下文

    参数：
        trace_id: 链路追踪ID
        request_id: 请求ID
    """
    bind_contextvars(trace_id=trace_id, request_id=request_id)


def get_context() -> dict:
    """获取当前上下文字典

    返回：
        上下文字典
    """
    return get_contextvars()


def clear_context() -> None:
    """清除上下文"""
    clear_contextvars()


@contextmanager
def request_context(trace_id: str = None, request_id: str = None):
    """请求级别上下文管理器

    参数：
        trace_id: 链路追踪ID
        request_id: 请求ID

    使用示例：
        with request_context(trace_id="trace-123", request_id="req-456"):
            logger.info("处理请求")
    """
    try:
        bind_contextvars(trace_id=trace_id, request_id=request_id)
        yield
    finally:
        clear_contextvars()
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\logger.py
```python
# datamind/logging/logger.py

"""日志API

提供统一的日志获取接口。
"""

import structlog
from typing import Optional


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """获取日志实例

    参数：
        name: 日志名称（可选）

    返回：
        structlog.BoundLogger 实例

    使用示例：
        from datamind.logging import get_logger

        logger = get_logger(__name__)
        logger.info("用户登录成功", user_id=123, action="login")
    """
    return structlog.get_logger(name)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\processors.py
```python
# datamind/logging/processors.py

"""structlog 处理器

提供日志增强处理器链，包括时间戳、脱敏、采样等。

核心功能：
  - add_timestamp: 添加时间戳（带时区）
  - mask_sensitive: 敏感信息脱敏
  - sampling: 日志采样

使用示例：
  from datamind.logging.processors import add_timestamp, mask_sensitive

  processors = [
      add_timestamp("Asia/Shanghai"),
      mask_sensitive(),
      sampling(0.5),
  ]
"""

import random
import structlog
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Set, Optional


# 敏感字段集合
_SENSITIVE_KEYS: Set[str] = {
    "password", "passwd", "pwd",
    "secret", "token",
    "access_token", "refresh_token",
    "api_key", "apikey",
    "authorization", "auth",
    "credential", "private_key",
}


def add_timestamp(timezone: str, date_format: Optional[str] = None):
    """添加时间戳处理器（带时区）

    参数：
        timezone: 时区字符串，如 Asia/Shanghai
        date_format: 日期格式，如 %Y-%m-%d %H:%M:%S，不提供则使用 ISO 格式

    返回：
        时间戳处理器函数
    """
    tz = ZoneInfo(timezone)

    def processor(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(tz)
        event_dict["timestamp"] = (
            now.strftime(date_format) if date_format else now.isoformat()
        )
        return event_dict

    return processor


def mask_sensitive(mask_char: str = "*", prefix: int = 2, suffix: int = 2):
    """敏感信息脱敏处理器

    参数：
        mask_char: 脱敏字符
        prefix: 前面保留位数
        suffix: 后面保留位数

    返回：
        脱敏处理器函数
    """
    def processor(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        for key in list(event_dict.keys()):
            if any(s in key.lower() for s in _SENSITIVE_KEYS):
                value = event_dict[key]

                if isinstance(value, str):
                    length = len(value)
                    if length <= prefix + suffix:
                        event_dict[key] = mask_char * length
                    else:
                        event_dict[key] = (
                            value[:prefix]
                            + mask_char * (length - prefix - suffix)
                            + value[-suffix:]
                        )
                else:
                    event_dict[key] = mask_char * 8

        return event_dict

    return processor


def sampling(rate: float):
    """采样处理器

    参数：
        rate: 采样率，0.0 到 1.0 之间

    返回：
        采样处理器函数
    """
    if rate >= 1.0:
        return lambda _, __, event_dict: event_dict

    def processor(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        if random.random() > rate:
            raise structlog.DropEvent
        return event_dict

    return processor
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\retention.py
```python
# datamind/logging/retention.py

"""日志保留管理

提供日志文件清理功能，自动删除超过保留天数的日志文件。

核心功能：
  - cleanup_logs: 清理过期日志文件
  - start_retention_worker: 启动定期清理后台线程

使用示例：
  from datamind.logging.retention import start_retention_worker

  start_retention_worker(config)
"""

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading
import time
import structlog

logger = structlog.get_logger(__name__)


def cleanup_logs(log_dir: Path, retention_days: int, timezone: str) -> None:
    """清理过期日志文件

    参数：
        log_dir: 日志目录路径
        retention_days: 日志保留天数
        timezone: 时区
    """
    if retention_days <= 0:
        return

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    expire = now - timedelta(days=retention_days)

    for file in log_dir.glob("*.log*"):
        try:
            mtime = datetime.fromtimestamp(file.stat().st_mtime, tz)

            if mtime < expire:
                file.unlink()
                logger.debug("删除过期日志文件", file=str(file))

        except FileNotFoundError:
            pass
        except PermissionError:
            logger.warning("权限不足，无法删除日志文件", file=str(file))
        except OSError as e:
            logger.warning("删除日志文件失败", file=str(file), error=str(e))


def start_retention_worker(config) -> None:
    """启动定期清理后台线程

    参数：
        config: 日志配置对象（需包含 dir、retention_days、timezone 属性）
    """
    def worker():
        while True:
            cleanup_logs(
                config.dir,
                config.retention_days,
                config.timezone,
            )
            time.sleep(3600)  # 每小时检查一次

    thread = threading.Thread(
        target=worker,
        daemon=True,
        name="datamind-log-retention",
    )
    thread.start()
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\setup.py
```python
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
    config.dir.mkdir(parents=True, exist_ok=True)

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
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\logging\\\_\_init\_\_.py
```python
# datamind/logging/__init__.py

"""日志模块

基于 structlog 的结构化日志系统，支持 JSON 和文本两种输出格式。

核心功能：
  - setup_logging: 初始化日志系统
  - get_logger: 获取日志实例
  - set_context: 设置上下文（trace_id / request_id）
  - get_context: 获取当前上下文
  - clear_context: 清除上下文
  - request_context: 请求级别上下文管理器

使用示例：
  from datamind.logging import setup_logging, get_logger, request_context

  # 初始化日志系统
  setup_logging(settings.logging)

  # 使用上下文管理器
  with request_context(trace_id="trace-123456", request_id="req-789"):
      logger = get_logger(__name__)
      logger.info("用户登录成功", user_id=123, action="login")
"""

from datamind.logging.context import (
    set_context,
    get_context,
    clear_context,
    request_context,
)
from datamind.logging.logger import get_logger
from datamind.logging.setup import setup_logging

__all__ = [
    "setup_logging",
    "get_logger",
    "set_context",
    "get_context",
    "clear_context",
    "request_context",
]
```
