# Datamind/datamind/core/logging/context.py

"""请求上下文管理

提供请求ID、链路追踪ID(trace_id)、调用层级ID(span_id)的上下文管理。

使用 contextvars 实现异步安全的上下文传递，支持：
  - 请求ID管理（request_id）
  - 链路追踪（trace_id）
  - 调用层级追踪（span_id）
  - 嵌套调用上下文（SpanContext）
  - 完整请求上下文（RequestContext）
  - 装饰器支持（with_span, with_request_id）
"""

import uuid
import contextvars
from typing import Optional, Callable, Any, TypeVar, cast

from datamind.core.logging.debug import debug_print

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])

# 上下文变量
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
_span_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="-")
_parent_span_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("parent_span_id", default="-")

# 配置引用（将在初始化时设置）
_config = None


def set_config(config: Any) -> None:
    """设置配置引用"""
    global _config
    _config = config


def _debug(msg: str, *args: Any) -> None:
    """调试输出"""
    if _config and _config.context_debug:
        debug_print("Context", msg, *args)


# Request ID 相关函数
def get_request_id() -> str:
    """获取当前请求ID"""
    request_id = _request_id_ctx.get()
    _debug("获取请求ID: %s", request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    """设置当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set(request_id)
    _debug("设置请求ID: %s -> %s", old_id, request_id)


def has_request_id() -> bool:
    """检查是否有请求ID"""
    has_id = _request_id_ctx.get() != "-"
    _debug("检查请求ID是否存在: %s", has_id)
    return has_id


def clear_request_id() -> None:
    """清除当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set("-")
    _debug("清除请求ID: %s -> -", old_id)


# Trace ID 相关函数
def get_trace_id() -> str:
    """获取当前 trace_id（链路追踪ID）"""
    trace_id = _trace_id_ctx.get()
    _debug("获取 trace_id: %s", trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """设置当前 trace_id（链路追踪ID）"""
    old_id = _trace_id_ctx.get()
    _trace_id_ctx.set(trace_id)
    _debug("设置 trace_id: %s -> %s", old_id, trace_id)


def has_trace_id() -> bool:
    """检查是否有 trace_id"""
    has_id = _trace_id_ctx.get() != "-"
    _debug("检查 trace_id 是否存在: %s", has_id)
    return has_id


# Span ID 相关函数
def get_span_id() -> str:
    """获取当前 span_id（调用层级ID）"""
    span_id = _span_id_ctx.get()
    _debug("获取 span_id: %s", span_id)
    return span_id


def set_span_id(span_id: str) -> None:
    """设置当前 span_id（调用层级ID）"""
    old_id = _span_id_ctx.get()
    _span_id_ctx.set(span_id)
    _debug("设置 span_id: %s -> %s", old_id, span_id)


def has_span_id() -> bool:
    """检查是否有 span_id"""
    has_id = _span_id_ctx.get() != "-"
    _debug("检查 span_id 是否存在: %s", has_id)
    return has_id


def get_parent_span_id() -> str:
    """获取当前父 span_id"""
    parent_id = _parent_span_id_ctx.get()
    _debug("获取 parent_span_id: %s", parent_id)
    return parent_id


# 辅助函数
def ensure_trace(create_trace: bool = True, create_request: bool = True) -> None:
    """确保 trace 存在（入口调用）

    参数:
        create_trace: 是否创建 trace_id（如果不存在）
        create_request: 是否创建 request_id（如果不存在）
    """
    if create_trace and _trace_id_ctx.get() == "-":
        trace_id = f"trace-{uuid.uuid4().hex[:16]}"
        set_trace_id(trace_id)

    if create_request and _request_id_ctx.get() == "-":
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        set_request_id(request_id)


def generate_request_id(prefix: str = "req") -> str:
    """生成新的请求ID"""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def generate_trace_id(prefix: str = "trace") -> str:
    """生成新的链路ID"""
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def generate_span_id(prefix: str = "span") -> str:
    """生成新的调用层级ID"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def get_context() -> dict:
    """获取当前完整的请求上下文"""
    return {
        'request_id': get_request_id(),
        'trace_id': get_trace_id(),
        'span_id': get_span_id(),
        'parent_span_id': get_parent_span_id(),
    }


def set_context(request_id: Optional[str] = None,
                trace_id: Optional[str] = None,
                span_id: Optional[str] = None,
                parent_span_id: Optional[str] = None) -> None:
    """批量设置上下文

    参数:
        request_id: 请求ID
        trace_id: 链路追踪ID
        span_id: 调用层级ID
        parent_span_id: 父调用层级ID
    """
    if request_id is not None:
        set_request_id(request_id)
    if trace_id is not None:
        set_trace_id(trace_id)
    if span_id is not None:
        set_span_id(span_id)
    if parent_span_id is not None:
        _parent_span_id_ctx.set(parent_span_id)


def reset_context() -> None:
    """重置所有上下文变量（主要用于测试）"""
    _request_id_ctx.set("-")
    _trace_id_ctx.set("-")
    _span_id_ctx.set("-")
    _parent_span_id_ctx.set("-")
    _debug("重置所有上下文")


# 上下文管理器
class SpanContext:
    """Span 上下文（支持嵌套调用）"""

    def __init__(self, name: Optional[str] = None, metadata: Optional[dict] = None):
        """
        参数:
            name: Span名称
            metadata: 额外的元数据
        """
        self.name = name
        self.metadata = metadata or {}
        self.old_span: Optional[str] = None
        self.old_parent: Optional[str] = None

    def __enter__(self) -> 'SpanContext':
        # 保存当前状态
        self.old_span = get_span_id()
        self.old_parent = get_parent_span_id()

        # 生成新的 span_id
        new_span = generate_span_id()
        set_span_id(new_span)

        # 设置 parent_span_id 为进入前的 span_id
        if self.old_span != "-":
            _parent_span_id_ctx.set(self.old_span)

        _debug("进入 span: %s (parent: %s, name: %s)",
               new_span, get_parent_span_id(), self.name)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 恢复父 span
        if self.old_parent is not None:
            _parent_span_id_ctx.set(self.old_parent)
        # 恢复当前 span
        set_span_id(self.old_span if self.old_span is not None else "-")
        _debug("退出 span -> %s", get_span_id())


class RequestIdContext:
    """请求ID上下文管理器"""

    def __init__(self, request_id: Optional[str] = None):
        """
        参数:
            request_id: 请求ID，如果不提供则不设置
        """
        self.request_id = request_id
        self.old_id: Optional[str] = None

    def __enter__(self) -> 'RequestIdContext':
        self.old_id = get_request_id()
        if self.request_id:
            set_request_id(self.request_id)
        _debug("进入请求ID上下文: %s", get_request_id())
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        set_request_id(self.old_id if self.old_id is not None else "-")
        _debug("退出请求ID上下文: %s", get_request_id())


class RequestContext:
    """完整请求上下文"""

    def __init__(self, request_id: Optional[str] = None, trace_id: Optional[str] = None):
        """
        参数:
            request_id: 请求ID
            trace_id: 链路追踪ID
        """
        self.request_id = request_id
        self.trace_id = trace_id
        self.old_request: Optional[str] = None
        self.old_trace: Optional[str] = None

    def __enter__(self) -> 'RequestContext':
        self.old_request = get_request_id()
        self.old_trace = get_trace_id()

        if self.request_id:
            set_request_id(self.request_id)
        if self.trace_id:
            set_trace_id(self.trace_id)

        _debug("进入请求上下文: request_id=%s, trace_id=%s",
               get_request_id(), get_trace_id())

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        set_request_id(self.old_request if self.old_request is not None else "-")
        set_trace_id(self.old_trace if self.old_trace is not None else "-")

        _debug("退出请求上下文")


# 装饰器
def with_request_id(request_id: Optional[str] = None) -> Callable[[F], F]:
    """装饰器：在函数执行期间设置请求ID

    参数:
        request_id: 请求ID，如果不提供则生成新的
    """

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            old_id = get_request_id()
            try:
                actual_request_id = request_id if request_id else generate_request_id()
                set_request_id(actual_request_id)
                _debug("装饰器设置请求ID: %s", get_request_id())
                return func(*args, **kwargs)
            finally:
                set_request_id(old_id)
                _debug("装饰器恢复请求ID: %s", old_id)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return cast(F, wrapper)

    return decorator


def with_span(name: Optional[str] = None) -> Callable[[F], F]:
    """装饰器：在函数执行期间创建 span

    参数:
        name: Span名称，默认使用函数名
    """

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with SpanContext(name or func.__name__):
                return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return cast(F, wrapper)

    return decorator