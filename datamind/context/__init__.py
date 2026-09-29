"""上下文模块.

基于 structlog.contextvars 实现请求级上下文传递，
支持异步任务、并发场景和嵌套作用域。

核心功能：
  - set_context: 清除现有上下文并设置新上下文
  - get_context: 获取当前上下文
  - clear_context: 清除当前上下文
  - update_context: 追加或覆盖上下文字段
  - context_scope: 创建临时上下文作用域
  - generate_trace_id: 生成链路追踪 ID
  - is_valid_trace_id: 校验链路追踪 ID
  - Context: 标准上下文字典类型

使用示例：
  from datamind.context import (
      clear_context,
      context_scope,
      generate_trace_id,
      get_context,
      is_valid_trace_id,
      set_context,
      update_context,
  )

  # 生成链路追踪 ID
  trace_id = generate_trace_id()

  # 设置上下文
  set_context(
      trace_id=trace_id,
      request_id="req_0123456789abcdef",
  )

  # 获取上下文
  context = get_context()

  # 更新上下文
  update_context(
      user="admin",
      ip="192.168.1.100",
  )

  # 校验链路追踪 ID
  if is_valid_trace_id(
      context.get(
          "trace_id"
      )
  ):
      print(
          context
      )

  # 创建临时上下文作用域
  with context_scope(
      trace_id=generate_trace_id(),
  ):
      do_something()

  # 清除上下文
  clear_context()
"""

from datamind.context.core import (
    clear_context,
    get_context,
    set_context,
    update_context,
)
from datamind.context.scope import context_scope
from datamind.context.tracing import (
    generate_trace_id,
    is_valid_trace_id,
)
from datamind.context.types import Context


__all__ = [
    "Context",
    "set_context",
    "get_context",
    "clear_context",
    "update_context",
    "context_scope",
    "generate_trace_id",
    "is_valid_trace_id",
]
