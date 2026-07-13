# datamind/context/scope.py

"""上下文作用域工具

提供基于 contextvars 的临时上下文作用域管理，
适用于请求、批处理、任务和异步场景，并支持嵌套。

核心功能：
  - context_scope: 创建临时上下文作用域

使用示例：
  from datamind.context.scope import context_scope

  # 创建外层上下文作用域
  with context_scope(
      user="admin",
  ):
      # 创建内层上下文作用域
      with context_scope(
          trace_id="0123456789abcdef0123456789abcdef",
      ):
          # 此时上下文同时包含 user 和 trace_id
          logger.info(
              "处理请求"
          )

      # 退出内层作用域后，trace_id 消失，user 仍然存在

  # 退出外层作用域后，user 消失
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from datamind.context.core import (
    get_context,
    set_context,
)


@contextmanager
def context_scope(
        **kwargs: Any,
) -> Iterator[None]:
    """创建临时上下文作用域

    当前上下文与传入字段合并。
    退出作用域时恢复进入前的上下文，支持嵌套使用。

    参数：
        **kwargs: 临时上下文字段
    """
    previous_context = get_context().copy()
    current_context = {
        **previous_context,
        **kwargs,
    }

    try:
        # 设置合并后的临时上下文
        set_context(
            **current_context
        )
        yield

    finally:
        # 恢复进入作用域前的上下文
        set_context(
            **previous_context
        )
