"""上下文核心.

基于 structlog.contextvars 实现请求级上下文传递，
支持异步任务和并发场景。

核心功能：
  - set_context: 清除现有上下文并设置新上下文
  - get_context: 获取当前上下文
  - clear_context: 清除当前上下文
  - update_context: 追加或覆盖上下文字段

使用示例：
  from datamind.context.core import (
      clear_context,
      get_context,
      set_context,
      update_context,
  )

  # 设置上下文
  set_context(
      trace_id="0123456789abcdef0123456789abcdef",
      request_id="req_0123456789abcdef",
  )

  # 获取上下文
  context = get_context()

  # 更新上下文
  update_context(
      user="admin",
  )

  # 清除上下文
  clear_context()
"""

from typing import Any

from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)


def set_context(
        **kwargs: Any,
) -> None:
    """设置上下文.

    清除所有现有上下文，然后设置新上下文。

    参数：
        **kwargs: 上下文字段
    """
    clear_contextvars()

    if kwargs:
        bind_contextvars(
            **kwargs
        )


def get_context() -> dict[str, Any]:
    """获取当前上下文.

    返回：
        当前上下文字典
    """
    return get_contextvars()


def clear_context() -> None:
    """清除当前上下文."""
    clear_contextvars()


def update_context(
        **kwargs: Any,
) -> None:
    """更新上下文.

    追加或覆盖指定字段，不影响其他字段。

    参数：
        **kwargs: 需要追加或覆盖的上下文字段
    """
    if kwargs:
        bind_contextvars(
            **kwargs
        )
