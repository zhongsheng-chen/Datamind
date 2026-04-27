# datamind/logging/render.py

"""日志渲染器

提供文本和 JSON 两种格式的日志渲染器。

核心功能：
  - text_renderer: 文本格式渲染器（控制台/文件）
  - json_renderer: JSON 格式渲染器（文件）

使用示例：
  from datamind.logging.render import text_renderer, json_renderer

  text_renderer = text_renderer()
  json_renderer = json_renderer()
"""

from typing import Dict, Any
import structlog

from datamind.context.keys import ALL_KEYS


def text_renderer():
    """文本格式日志渲染器

    格式：
        time | level | [trace_id] | [request_id] | [user] | [ip] | event | kv

    说明：
        - trace_id / request_id / user / ip：存在时才输出（key=value）
        - event：主日志内容
        - kv：额外字段（key=value，逗号分隔）

    返回：
        文本渲染器函数
    """
    def renderer(_, __, event_dict: Dict[str, Any]) -> str:
        cols = [
            event_dict.pop("timestamp") or "-",
            f"{event_dict.pop('level', '').upper():<8}",
        ]

        for key in ALL_KEYS:
            value = event_dict.pop(key, None)
            if value:
                cols.append(str(value))

        cols.append(event_dict.pop("event", ""))

        msg = " | ".join(cols)

        if event_dict:
            msg += " | " + ", ".join(
                f"{k}={v}" for k, v in sorted(event_dict.items())
            )

        return msg

    return renderer


def json_renderer():
    """JSON 格式日志渲染器

    返回：
        JSON 渲染器函数
    """
    return structlog.processors.JSONRenderer()