# datamind/utils/__init__.py

"""通用工具模块

提供日期时间处理、ID 生成和网络信息获取等通用工具能力。

核心功能：
  - get_timezone: 获取当前配置时区
  - parse_datetime: 解析 ISO 8601 日期时间字符串
  - to_utc: 将日期时间转换为 UTC
  - to_local: 将日期时间转换为本地时区
  - format_datetime: 格式化本地日期时间
  - format_iso_utc: 格式化为 ISO 8601 UTC 字符串
  - generate_id: 根据前缀和键值生成确定性 ID
  - generate_random_id: 根据前缀生成随机 ID
  - get_host_ip: 获取当前主机 IP
  - get_hostname: 获取当前主机名

使用示例：
  from datamind.utils import (
      format_datetime,
      generate_random_id,
      get_host_ip,
      parse_datetime,
  )

  dt = parse_datetime(
      "2026-07-23T08:30:15Z"
  )
  formatted_dt = format_datetime(
      dt
  )
  event_id = generate_random_id(
      prefix="evt"
  )
  host_ip = get_host_ip()
"""

from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    get_timezone,
    parse_datetime,
    to_local,
    to_utc,
)
from datamind.utils.generator import (
    generate_id,
    generate_random_id,
)
from datamind.utils.network import (
    get_host_ip,
    get_hostname,
)


__all__ = [
    "format_datetime",
    "format_iso_utc",
    "generate_id",
    "generate_random_id",
    "get_host_ip",
    "get_hostname",
    "get_timezone",
    "parse_datetime",
    "to_local",
    "to_utc",
]
