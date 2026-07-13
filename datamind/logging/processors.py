# datamind/logging/processors.py

"""日志增强处理器

提供日志事件的时间戳补充、上下文补充、敏感信息脱敏和采样能力。

核心功能：
  - add_timestamp: 添加带时区的时间戳
  - add_context: 补充标准上下文字段
  - mask_sensitive: 递归脱敏敏感信息
  - sampling: 对普通日志进行采样，保留警告、错误和异常日志

使用示例：
  from datamind.logging.processors import (
      add_context,
      add_timestamp,
      mask_sensitive,
      sampling,
  )

  processors = [
      add_timestamp("Asia/Shanghai"),
      add_context(),
      mask_sensitive(),
      sampling(0.5),
  ]
"""

import random
from datetime import datetime
from typing import (
    Any,
    Final,
)
from zoneinfo import ZoneInfo

import structlog
from structlog.typing import (
    EventDict,
    Processor,
    WrappedLogger,
)

from datamind.context.keys import ALL_KEYS


_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "credential",
        "private_key",
    }
)
_UNSAMPLED_LEVELS: Final[frozenset[str]] = frozenset(
    {
        "warning",
        "error",
        "critical",
        "fatal",
    }
)


def add_timestamp(
        timezone: str,
        date_format: str | None = None,
) -> Processor:
    """添加带时区的时间戳

    参数：
        timezone: IANA 时区名称，如 Asia/Shanghai
        date_format: 日期格式，None 表示使用 ISO 8601 格式

    返回：
        时间戳处理器函数

    异常：
        ZoneInfoNotFoundError: 时区名称无效
    """
    tz = ZoneInfo(timezone)

    def processor(
            _: WrappedLogger,
            __: str,
            event_dict: EventDict,
    ) -> EventDict:
        now = datetime.now(tz)

        event_dict["timestamp"] = (
            now.strftime(date_format)
            if date_format
            else now.isoformat()
        )

        return event_dict

    return processor


def add_context() -> Processor:
    """补充标准上下文字段

    已存在的事件字段优先，
    不会被当前上下文中的同名字段覆盖。

    返回：
        上下文字段处理器函数
    """

    def processor(
            _: WrappedLogger,
            __: str,
            event_dict: EventDict,
    ) -> EventDict:
        context = structlog.contextvars.get_contextvars()

        for key in ALL_KEYS:
            value = context.get(key)

            if value is not None:
                event_dict.setdefault(
                    key,
                    value,
                )

        return event_dict

    return processor


def mask_sensitive(
        mask_char: str = "*",
        prefix: int = 2,
        suffix: int = 2,
) -> Processor:
    """递归脱敏敏感信息

    参数：
        mask_char: 脱敏字符，只能包含一个字符
        prefix: 前面保留位数
        suffix: 后面保留位数

    返回：
        敏感信息脱敏处理器函数

    异常：
        ValueError: 脱敏字符或保留位数无效
    """
    if not mask_char:
        raise ValueError(
            "mask_char 不能为空"
        )

    if len(mask_char) != 1:
        raise ValueError(
            "mask_char 只能包含一个字符，"
            f"当前值：{mask_char}"
        )

    if prefix < 0:
        raise ValueError(
            "prefix 必须大于等于 0，"
            f"当前值：{prefix}"
        )

    if suffix < 0:
        raise ValueError(
            "suffix 必须大于等于 0，"
            f"当前值：{suffix}"
        )

    def is_sensitive_key(key: str) -> bool:
        normalized_key = key.lower()

        return any(
            sensitive_key in normalized_key
            for sensitive_key in _SENSITIVE_KEYS
        )

    def mask_string(value: str) -> str:
        length = len(value)

        if length <= prefix + suffix:
            return mask_char * length

        visible_prefix = value[:prefix] if prefix else ""
        visible_suffix = value[-suffix:] if suffix else ""
        masked_length = length - prefix - suffix

        return (
            visible_prefix
            + mask_char * masked_length
            + visible_suffix
        )

    def mask_value(value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, str):
            return mask_string(value)

        return mask_char * 8

    def mask_nested(
            value: Any,
            force_mask: bool = False,
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: mask_nested(
                    item,
                    force_mask=(
                        force_mask
                        or is_sensitive_key(str(key))
                    ),
                )
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                mask_nested(item, force_mask)
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                mask_nested(item, force_mask)
                for item in value
            )

        if force_mask:
            return mask_value(value)

        return value

    def processor(
            _: WrappedLogger,
            __: str,
            event_dict: EventDict,
    ) -> EventDict:
        return mask_nested(event_dict)

    return processor


def sampling(rate: float) -> Processor:
    """对普通日志进行采样

    warning、error、critical、fatal 级别以及包含异常信息的日志
    不参与采样，始终保留。

    参数：
        rate: 普通日志采样率，范围为 0.0 到 1.0

    返回：
        日志采样处理器函数

    异常：
        ValueError: 采样率不在有效范围内
    """
    if not 0 <= rate <= 1:
        raise ValueError(
            "rate 必须在 0.0 到 1.0 之间，"
            f"当前值：{rate}"
        )

    if rate == 1:
        return lambda _, __, event_dict: event_dict

    def processor(
            _: WrappedLogger,
            __: str,
            event_dict: EventDict,
    ) -> EventDict:
        level = str(
            event_dict.get(
                "level",
                "",
            )
        ).lower()

        if (
            level in _UNSAMPLED_LEVELS
            or event_dict.get("exc_info")
            or event_dict.get("exception")
        ):
            return event_dict

        if random.random() >= rate:
            raise structlog.DropEvent

        return event_dict

    return processor
