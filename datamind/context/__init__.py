# datamind/context/__init__.py

"""上下文模块

基于 structlog.contextvars 实现请求级别的上下文传递，支持异步和并发场景。

核心功能：
  - set_context: 设置上下文
  - get_context: 获取当前上下文
  - clear_context: 清除上下文
  - update_context: 更新上下文（覆盖已有字段）
  - context_scope: 临时上下文作用域管理器

使用示例：
  from datamind.context import set_context, get_context, update_context, context_scope

  # 设置上下文
  set_context(trace_id="trace-123", request_id="req-456")

  # 获取上下文
  ctx = get_context()

  # 更新上下文
  update_context(user="admin", ip="192.168.1.100")

  # 临时作用域
  with context_scope(trace_id="new-trace"):
      do_something()
"""

from datamind.context.core import set_context, get_context, clear_context, update_context
from datamind.context.scope import context_scope
from datamind.context.types import Context

__all__ = [
    "set_context",
    "get_context",
    "clear_context",
    "update_context",
    "context_scope",
    "Context",
]