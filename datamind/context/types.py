# datamind/context/types.py

"""上下文类型定义

定义上下文字典的类型结构，提供类型提示支持。

核心功能：
  - Context: 上下文字典类型

使用示例：
  from datamind.context.types import Context

  ctx: Context = {
      "trace_id": "trace-123",
      "request_id": "req-456",
      "source": "api",
      "user": "admin",
      "ip": "192.168.1.100",
      "hostname": "host",
  }
"""

from typing import TypedDict


class Context(TypedDict, total=False):
    """上下文字典类型

    属性：
        trace_id: 链路追踪 ID
        request_id: 请求 ID
        source: 请求 ID
        user: 操作用户
        ip: 客户端 IP 地址
        hostname: 客户端名称
    """
    trace_id: str
    request_id: str
    source: str
    user: str
    ip: str
    hostname: str