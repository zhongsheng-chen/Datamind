# datamind/utils/datetime.py

"""日期时间工具

提供时区转换和格式化功能。

核心功能：
  - get_timezone: 获取配置的时区
  - to_utc: 转换为 UTC 时间
  - to_local: 转换为本地时间
  - format_datetime: 格式化日期时间
  - format_iso_utc: 格式化为 ISO 8601 UTC

使用示例：
  from datamind.utils.datetime import to_utc, to_local, format_datetime, format_iso_utc

  # 转换为 UTC
  utc_dt = to_utc(datetime.now())

  # 转换为本地时间
  local_dt = to_local(utc_dt)

  # 格式化日期时间
  formatted = format_datetime(local_dt)

  # 格式化为 ISO 8601 UTC
  iso = format_iso_utc(datetime.now())
"""

import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


def get_timezone() -> ZoneInfo:
    """获取配置的时区

    从环境变量 TZ 读取时区，未配置时返回 UTC。

    返回：
        ZoneInfo 实例
    """
    tz_name = os.getenv("TZ", "UTC")
    return ZoneInfo(tz_name)


def to_utc(dt: datetime | None) -> datetime | None:
    """转换为 UTC 时间

    参数：
        dt: 原始时间（带时区或不带时区）

    返回：
        UTC 时间，输入为 None 时返回 None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def to_local(dt: datetime | None) -> datetime | None:
    """转换为本地时间

    参数：
        dt: 原始时间（带时区或不带时区）

    返回：
        本地时间，输入为 None 时返回 None
    """
    if dt is None:
        return None

    tz = get_timezone()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(tz)


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间

    参数：
        dt: 原始时间
        fmt: 时间格式

    返回：
        格式化后的时间字符串，输入为 None 时返回 "-"
    """
    if dt is None:
        return "-"

    return to_local(dt).strftime(fmt)


def format_iso_utc(dt: datetime | None) -> str | None:
    """格式化为 ISO 8601 UTC 时间（毫秒精度）

    参数：
        dt: 原始时间

    返回：
        ISO 8601 UTC 字符串（如 2024-01-01T12:00:00.123Z），输入为 None 时返回 None
    """
    if dt is None:
        return None

    dt = to_utc(dt)

    # 对齐到毫秒
    dt = dt - timedelta(microseconds=dt.microsecond % 1000)

    ms = dt.microsecond // 1000

    return f"{dt:%Y-%m-%dT%H:%M:%S}.{ms:03d}Z"