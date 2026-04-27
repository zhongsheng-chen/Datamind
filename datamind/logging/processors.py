# datamind/logging/processors.py

"""日志增强处理器

提供日志事件的增强处理函数，包括时间戳、上下文字段、脱敏、采样等。

核心功能：
  - add_timestamp: 添加时间戳（带时区）
  - add_context: 补齐基础上下文字段
  - mask_sensitive: 敏感信息脱敏
  - sampling: 日志采样

使用示例：
  from datamind.logging.processors import add_timestamp, mask_sensitive, sampling

  processors = [
      add_timestamp("Asia/Shanghai"),
      add_context(),
      mask_sensitive(),
      sampling(0.5),
  ]
"""

import random
import structlog
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Set, Optional

from datamind.context.keys import ALL_KEYS


_SENSITIVE_KEYS: Set[str] = {
    "password", "passwd", "pwd",
    "secret", "token",
    "access_token", "refresh_token",
    "api_key", "apikey",
    "authorization", "auth",
    "credential", "private_key",
}


def add_timestamp(timezone: str, date_format: Optional[str] = None):
    """添加时间戳（带时区）

    参数：
        timezone: 时区字符串，如 Asia/Shanghai
        date_format: 日期格式，不提供则使用 ISO 格式

    返回：
        时间戳处理器函数
    """
    tz = ZoneInfo(timezone)

    def processor(_, __, event_dict: Dict[str, Any]):
        now = datetime.now(tz)
        event_dict["timestamp"] = (
            now.strftime(date_format) if date_format else now.isoformat()
        )
        return event_dict

    return processor


def add_context():
    """添加上下文字段

    补齐基础上下文字段，避免 render 层做防御判断。

    返回：
        上下文字段处理器函数
    """
    def processor(_, __, event_dict):
        ctx = structlog.contextvars.get_contextvars()

        for key in ALL_KEYS:
            value = ctx.get(key)
            if value is not None:
                event_dict[key] = value

        return event_dict

    return processor


def mask_sensitive(mask_char: str = "*", prefix: int = 2, suffix: int = 2):
    """敏感信息脱敏

    参数：
        mask_char: 脱敏字符
        prefix: 前面保留位数
        suffix: 后面保留位数

    返回：
        脱敏处理器函数
    """
    def is_sensitive_key(key: str) -> bool:
        k = key.lower()
        return any(s in k for s in _SENSITIVE_KEYS)

    def processor(_, __, event_dict: Dict[str, Any]):
        if not any(is_sensitive_key(k) for k in event_dict.keys()):
            return event_dict

        for key in list(event_dict.keys()):
            if not is_sensitive_key(key):
                continue

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
    """日志采样

    参数：
        rate: 采样率，0.0 到 1.0 之间

    返回：
        采样处理器函数
    """
    if rate >= 1.0:
        return lambda _, __, event_dict: event_dict

    def processor(_, __, event_dict: Dict[str, Any]):
        if random.random() > rate:
            raise structlog.DropEvent
        return event_dict

    return processor