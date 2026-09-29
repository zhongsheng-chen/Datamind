"""上下文键定义.

定义请求上下文中使用的标准字段名。

核心功能：
  - TRACE_ID: 链路追踪 ID
  - REQUEST_ID: 请求 ID
  - SOURCE: 请求来源
  - USER: 操作用户
  - IP: 客户端 IP 地址
  - HOSTNAME: 客户端主机名称
  - ALL_KEYS: 所有标准上下文键

使用示例：
  from datamind.context.keys import (
      ALL_KEYS,
      HOSTNAME,
      IP,
      REQUEST_ID,
      SOURCE,
      TRACE_ID,
      USER,
  )

  context = {
      TRACE_ID: "0123456789abcdef0123456789abcdef",
      REQUEST_ID: "req_0123456789abcdef",
      SOURCE: "http",
      USER: "admin",
      IP: "192.168.1.100",
      HOSTNAME: "client",
  }

  missing = set(
      ALL_KEYS
  ) - set(
      context
  )
"""

from typing import Final


TRACE_ID: Final[str] = "trace_id"
REQUEST_ID: Final[str] = "request_id"
SOURCE: Final[str] = "source"
USER: Final[str] = "user"
IP: Final[str] = "ip"
HOSTNAME: Final[str] = "hostname"

ALL_KEYS: Final[tuple[str, ...]] = (
    TRACE_ID,
    REQUEST_ID,
    SOURCE,
    USER,
    IP,
    HOSTNAME,
)


__all__ = [
    "TRACE_ID",
    "REQUEST_ID",
    "SOURCE",
    "USER",
    "IP",
    "HOSTNAME",
    "ALL_KEYS",
]
