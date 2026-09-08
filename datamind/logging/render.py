"""日志渲染器

提供文本和 JSON 两种格式的日志渲染能力。

核心功能：
  - text_renderer: 创建文本格式日志渲染器
  - json_renderer: 创建 JSON 格式日志渲染器

使用示例：
  from datamind.logging.render import (
      json_renderer,
      text_renderer,
  )

  text_processor = text_renderer()
  json_processor = json_renderer()
"""

from collections.abc import Callable
from typing import Final

import structlog
from structlog.typing import (
    EventDict,
    WrappedLogger,
)

from datamind.context.keys import ALL_KEYS


Renderer = Callable[
    [
        WrappedLogger,
        str,
        EventDict,
    ],
    str,
]

_PROCESSOR_META_KEYS: Final[tuple[str, ...]] = (
    "_record",
    "_from_structlog",
)


def _copy_event(event_dict: EventDict) -> EventDict:
    """复制日志事件并移除处理器内部字段

    参数：
        event_dict: 原始日志事件

    返回：
        移除处理器内部字段后的事件副本
    """
    event = dict(event_dict)

    for key in _PROCESSOR_META_KEYS:
        event.pop(key, None)

    return event


def text_renderer() -> Renderer:
    """创建文本格式日志渲染器

    格式：
        timestamp | level | context | event | fields

    说明：
        - context: 按标准顺序输出存在的上下文字段
        - event: 主日志内容
        - fields: 其余字段，使用 key=value 格式输出

    返回：
        文本格式渲染器函数
    """

    def renderer(
            _: WrappedLogger,
            __: str,
            event_dict: EventDict,
    ) -> str:
        event = _copy_event(event_dict)

        timestamp = str(event.pop("timestamp", "") or "-")
        level = str(event.pop("level", "")).upper()

        columns = [
            timestamp,
            f"{level:<8}",
        ]

        for key in ALL_KEYS:
            value = event.pop(key, None)

            if value is not None and value != "":
                columns.append(f"{key}={value}")

        columns.append(str(event.pop("event", "")))

        message = " | ".join(columns)

        if event:
            fields = ", ".join(
                f"{key}={value}"
                for key, value in event.items()
            )
            message = f"{message} | {fields}"

        return message

    return renderer


def json_renderer() -> Renderer:
    """创建 JSON 格式日志渲染器

    返回：
        JSON 格式渲染器函数
    """
    json_processor = structlog.processors.JSONRenderer()

    def renderer(
            logger: WrappedLogger,
            method_name: str,
            event_dict: EventDict,
    ) -> str:
        event = _copy_event(event_dict)

        result = json_processor(
            logger,
            method_name,
            event,
        )

        if isinstance(result, bytes):
            return result.decode("utf-8")

        return result

    return renderer
