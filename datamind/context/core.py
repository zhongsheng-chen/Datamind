# datamind/context/core.py

"""上下文核心

基于 structlog.contextvars 实现请求级别的上下文传递，支持异步和并发场景。

核心功能：
  - set_context: 设置上下文
  - get_context: 获取当前上下文
  - clear_context: 清除上下文
  - update_context: 更新上下文（覆盖已有字段）

使用示例：
  from datamind.context.core import set_context, get_context, update_context

  set_context(trace_id="trace-123", request_id="req-456")
  ctx = get_context()
  update_context(user="admin", ip="192.168.1.100")
"""

from structlog.contextvars import (
    bind_contextvars,
    get_contextvars,
    clear_contextvars,
)


def set_context(**kwargs):
    """设置上下文

    参数：
        **kwargs: 上下文字段
    """
    bind_contextvars(**kwargs)


def get_context():
    """获取当前上下文

    返回：
        上下文字典
    """
    return get_contextvars()


def clear_context():
    """清除上下文"""
    clear_contextvars()


def update_context(**kwargs):
    """更新上下文（覆盖已有字段）

    参数：
        **kwargs: 需要更新/覆盖的字段
    """
    bind_contextvars(**kwargs)