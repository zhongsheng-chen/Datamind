utils组件

## Project Structure
```
    __init__.py
    __pycache__/
    datetime.py
    generator.py
    network.py
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\utils\\datetime.py
```python
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
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\utils\\generator.py
```python
# datamind/utils/id.py

"""ID 生成工具

提供统一的 ID 生成能力，支持确定性 ID 与随机 ID 两种模式。

核心功能：
  - generate_id: 基于前缀和键值生成确定性 ID，用于实体对象
  - generate_random_id: 生成随机 ID，用于事件类对象

使用示例：
    from datamind.utils.id import generate_id, generate_random_id

    # 生成模型 ID
    model_id = generate_id(
        prefix="mdl",
        keys=(name,),
    )

    # 生成版本 ID
    version_id = generate_id(
        prefix="ver",
        keys=(model_id, version),
    )

    # 生成部署 ID
    deployment_id = generate_random_id(prefix="dep")
"""

import hashlib
import uuid


def generate_id(
    *,
    prefix: str,
    keys: tuple[str, ...],
) -> str:
    """生成唯一 ID

    基于 prefix 和 keys 计算 MD5 哈希生成稳定 ID，
    相同输入始终生成相同 ID。

    参数：
        prefix: ID 前缀
        keys: 用于生成哈希的键值列表

    返回：
        格式为 {prefix}_{8位MD5哈希} 的 ID
    """
    raw = ":".join(keys)

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

    return f"{prefix}_{digest}"

def generate_random_id(
    *,
    prefix: str,
) -> str:
    """生成随机 ID

    使用 UUID4 生成随机唯一 ID。

    参数：
        prefix: ID 前缀

    返回：
        格式为 {prefix}_{12位uuid} 的 ID
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\utils\\network.py
```python
# datamind/utils/network.py

"""网络工具

提供网络相关辅助能力。

核心功能：
  - get_host_ip: 获取当前主机 IP
  - get_hostname: 获取当前主机名

使用示例：
    from datamind.utils.network import (
        get_host_ip,
        get_hostname,
    )

    ip = get_host_ip()
    hostname = get_hostname()
"""

import socket


def get_host_ip() -> str:
    """获取当前主机 IP

    获取当前主机用于对外通信的 IP 地址。

    返回：
        当前主机 IP

    注意：
        返回的是当前主机出口 IP，
        不一定是公网 IP。
    """
    try:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as sock:
            sock.connect(("8.8.8.8", 80))

            return sock.getsockname()[0]

    except OSError:
        return "127.0.0.1"

def get_hostname() -> str:
    """获取当前主机名

    返回：
        当前主机名
    """
    return socket.gethostname()
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\utils\\\_\_init\_\_.py
```python

```
