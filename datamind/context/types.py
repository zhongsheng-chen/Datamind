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
      "user": "admin",
      "ip": "192.168.1.100",
  }
"""

from typing import TypedDict


class Context(TypedDict, total=False):
    """上下文字典类型

    属性：
        trace_id: 链路追踪ID
        request_id: 请求ID
        user: 操作用户
        ip: 客户端IP地址
    """
    trace_id: str
    request_id: str
    user: str
    ip: str