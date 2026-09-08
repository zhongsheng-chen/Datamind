"""上下文类型定义

定义请求上下文字典的类型结构，提供静态类型提示支持。

核心功能：
  - Context: 请求上下文字典类型

使用示例：
  from datamind.context.types import Context

  context: Context = {
      "trace_id": "0123456789abcdef0123456789abcdef",
      "request_id": "req_0123456789abcdef",
      "source": "http",
      "user": "admin",
      "ip": "192.168.1.100",
      "hostname": "client",
  }
"""

from typing import TypedDict


class Context(TypedDict, total=False):
    """请求上下文字典类型

    属性：
        trace_id: 链路追踪 ID
        request_id: 请求 ID
        source: 请求来源
        user: 操作用户
        ip: 客户端 IP 地址
        hostname: 客户端主机名称
    """

    trace_id: str
    request_id: str
    source: str
    user: str
    ip: str
    hostname: str
