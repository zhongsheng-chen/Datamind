# datamind/context/scope.py

"""上下文作用域工具

提供基于 contextvars 的临时上下文作用域管理。
适用于 request / batch / task / async 等所有场景，支持嵌套。

核心功能：
  - context_scope: 通用上下文作用域管理器（支持嵌套）

使用示例：
  from datamind.context.scope import context_scope

  with context_scope(user="admin"):
      with context_scope(trace_id="trace-123"):
          # 此时上下文同时包含 user 和 trace_id
          logger.info("处理请求")
      # 退出内层 scope 后，trace_id 消失，user 仍然存在
  # 退出外层 scope 后，user 消失
"""

from contextlib import contextmanager

from datamind.context.core import set_context, get_context


@contextmanager
def context_scope(**kwargs):
    """通用上下文作用域（支持嵌套）

    在内层 scope 中，上下文与外层合并；退出时恢复外层上下文。

    参数：
        **kwargs: 临时上下文字段

    使用示例：
        with context_scope(user="admin"):
            with context_scope(trace_id="trace-123"):
                do_something()
    """
    old = get_context().copy()

    try:
        # 合并上下文
        set_context(**{**old, **kwargs})
        yield
    finally:
        # 恢复旧上下文
        set_context(**old) if old else set_context()