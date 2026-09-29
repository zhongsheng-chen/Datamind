"""日期时间工具.

提供时区获取、UTC 转换、日期时间解析、
本地时间转换和格式化能力。

核心功能：
  - get_timezone: 获取当前配置时区
  - parse_datetime: 解析 ISO 8601 日期时间字符串
  - to_utc: 将日期时间转换为 UTC
  - to_local: 将日期时间转换为本地时区
  - format_datetime: 格式化本地日期时间
  - format_iso_utc: 格式化为 ISO 8601 UTC 字符串

使用示例：
  from datetime import datetime

  from datamind.utils.datetime import (
      format_datetime,
      format_iso_utc,
      parse_datetime,
      to_local,
      to_utc,
  )

  # 转换为 UTC 时间
  utc_dt = to_utc(
      datetime.now()
  )

  # 解析日期时间字符串
  parsed_dt = parse_datetime(
      "2026-06-25T09:00:00+08:00"
  )

  # 转换为本地时间
  local_dt = to_local(
      utc_dt
  )

  # 格式化本地时间
  formatted_dt = format_datetime(
      local_dt
  )

  # 格式化为 ISO 8601 UTC 时间
  iso_dt = format_iso_utc(
      datetime.now()
  )
"""

import os
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import overload
from zoneinfo import ZoneInfo


def get_timezone(
        timezone_name: str | None = None,
) -> ZoneInfo:
    """获取当前配置时区.

    优先使用显式传入的 IANA 时区名称，否则从环境变量 TZ 读取，
    两者均未配置时使用 UTC。

    参数：
        timezone_name: IANA 时区名称（可选）

    返回：
        当前配置的 ZoneInfo 实例
    """
    resolved_name = (
        timezone_name
        or os.getenv(
            "TZ",
            "UTC",
        )
    )

    return ZoneInfo(
        resolved_name
    )


def parse_datetime(
        raw: str | None,
        *,
        timezone_name: str | None = None,
) -> datetime | None:
    """解析日期时间并转换为 UTC.

    支持使用空格或 T 分隔日期与时间，以及 Z 或
    数值时区偏移。输入不含时区信息时使用 timezone_name，
    timezone_name 未提供时按 UTC 处理。

    参数：
        raw: 待解析的日期时间文本
        timezone_name: 无时区信息时使用的 IANA 时区名称（可选）

    返回：
        UTC 日期时间；raw 为 None 时返回 None

    异常：
        ValueError: raw 不是有效的日期时间
    """
    if raw is None:
        return None

    normalized = (
        f"{raw[:-1]}+00:00"
        if raw.endswith(
            "Z"
        )
        else raw
    )

    dt = datetime.fromisoformat(
        normalized
    )

    if dt.tzinfo is None and timezone_name is not None:
        dt = dt.replace(
            tzinfo=get_timezone(
                timezone_name
            )
        )

    return to_utc(
        dt
    )


@overload
def to_utc(
        dt: datetime,
) -> datetime:
    ...


@overload
def to_utc(
        dt: None,
) -> None:
    ...


@overload
def to_utc(
        dt: datetime | None,
) -> datetime | None:
    ...


def to_utc(
        dt: datetime | None,
) -> datetime | None:
    """将日期时间转换为 UTC.

    不带时区的日期时间按 UTC 处理。

    参数：
        dt: 待转换的日期时间

    返回：
        UTC 日期时间，输入为 None 时返回 None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


def to_local(
        dt: datetime | None,
        *,
        timezone_name: str | None = None,
) -> datetime | None:
    """将日期时间转换为本地时区.

    不带时区的日期时间按 UTC 处理。

    参数：
        dt: 待转换的日期时间
        timezone_name: IANA 时区名称（可选）

    返回：
        本地日期时间，输入为 None 时返回 None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    local_timezone = (
        get_timezone(
            timezone_name
        )
        if timezone_name is not None
        else get_timezone()
    )

    return dt.astimezone(
        local_timezone
    )


def format_datetime(
        dt: datetime | None,
        fmt: str = "%Y-%m-%d %H:%M:%S",
        *,
        timezone_name: str | None = None,
) -> str:
    """格式化本地日期时间.

    参数：
        dt: 待格式化的日期时间
        fmt: 日期时间格式
        timezone_name: IANA 时区名称（可选）

    返回：
        格式化后的字符串，输入为 None 时返回 "-"
    """
    local_dt = to_local(
        dt,
        timezone_name=timezone_name,
    )

    if local_dt is None:
        return "-"

    return local_dt.strftime(
        fmt
    )


def format_iso_utc(
        dt: datetime | None,
) -> str | None:
    """格式化为 ISO 8601 UTC 字符串.

    输出固定为毫秒精度，并使用 Z 表示 UTC。

    参数：
        dt: 待格式化的日期时间

    返回：
        ISO 8601 UTC 字符串，输入为 None 时返回 None
    """
    utc_dt = to_utc(
        dt
    )

    if utc_dt is None:
        return None

    utc_dt = utc_dt - timedelta(
        microseconds=(
            utc_dt.microsecond
            % 1000
        )
    )
    milliseconds = (
        utc_dt.microsecond
        // 1000
    )

    return (
        f"{utc_dt:%Y-%m-%dT%H:%M:%S}"
        f".{milliseconds:03d}Z"
    )
