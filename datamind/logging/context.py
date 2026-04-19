# datamind/logging/context.py

"""日志上下文

使用 structlog.contextvars 实现请求级别的上下文传递，支持异步和并发场景。

核心功能：
  - set_context: 设置上下文（trace_id / request_id）
  - get_context: 获取当前上下文字典
  - clear_context: 清除上下文
  - request_context: 上下文管理器，用于请求级别的作用域

使用示例：
  from datamind.logging.context import set_context, request_context

  # 全局设置
  set_context(trace_id="trace-123", request_id="req-456")

  # 请求级别作用域
  with request_context(trace_id="trace-789", request_id="req-012"):
      logger.info("处理请求")
"""

from contextlib import contextmanager
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)


def set_context(trace_id: str = None, request_id: str = None) -> None:
    """设置上下文

    参数：
        trace_id: 链路追踪ID
        request_id: 请求ID
    """
    bind_contextvars(trace_id=trace_id, request_id=request_id)


def get_context() -> dict:
    """获取当前上下文字典

    返回：
        上下文字典
    """
    return get_contextvars()


def clear_context() -> None:
    """清除上下文"""
    clear_contextvars()


@contextmanager
def request_context(trace_id: str = None, request_id: str = None):
    """请求级别上下文管理器

    参数：
        trace_id: 链路追踪ID
        request_id: 请求ID

    使用示例：
        with request_context(trace_id="trace-123", request_id="req-456"):
            logger.info("处理请求")
    """
    try:
        bind_contextvars(trace_id=trace_id, request_id=request_id)
        yield
    finally:
        clear_contextvars()