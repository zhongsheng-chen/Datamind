# datamind/context/scope.py

"""上下文作用域工具

提供基于 contextvars 的临时上下文作用域管理。
适用于 request / batch / task / async 等所有场景。

核心功能：
  - context_scope: 通用上下文作用域管理器

使用示例：
  from datamind.context.scope import context_scope

  with context_scope(trace_id="trace-123", request_id="req-456"):
      # 在这个作用域内，上下文已设置
      logger = get_logger(__name__)
      logger.info("处理请求")
  # 退出作用域后，上下文自动恢复
"""

from contextlib import contextmanager

from datamind.context.core import set_context, get_context, clear_context


@contextmanager
def context_scope(**kwargs):
    """通用上下文作用域

    在作用域内设置临时上下文，退出后自动恢复原有上下文。

    参数：
        **kwargs: 临时上下文字段

    使用示例：
        with context_scope(trace_id="trace-123", request_id="req-456"):
            # 临时上下文生效
            do_something()
        # 原有上下文恢复
    """
    old = get_context()

    try:
        set_context(**kwargs)
        yield
    finally:
        clear_context()
        if old:
            set_context(**old)