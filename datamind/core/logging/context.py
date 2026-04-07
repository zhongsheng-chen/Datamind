# datamind/core/logging/context.py

"""请求上下文管理

提供请求ID、链路追踪ID(trace_id)、调用层级ID(span_id)的上下文管理。

核心功能：
  - get/set request_id/trace_id/span_id: 获取/设置上下文变量
  - ensure_request/trace/span: 确保上下文存在
  - generate_request_id/trace_id/span_id: 生成新的ID
  - get_context/set_context: 批量获取/设置上下文
  - reset_context: 重置所有上下文（测试用）

特性：
  - 异步安全：使用 contextvars 实现异步上下文传递
  - 线程传递：支持跨线程上下文传递
  - 嵌套调用：支持 SpanContext 嵌套
  - 装饰器支持：with_request_id, with_span
  - 上下文管理器：RequestIdContext, SpanContext, RequestContext
  - 调试支持：可配置的调试输出

使用示例：
    from datamind.core.logging import context

    # 设置请求ID
    context.set_request_id("req-12345")

    # 获取当前请求ID
    request_id = context.get_request_id()

    # 使用上下文管理器
    with context.RequestIdContext("req-67890"):
        # 在此上下文中请求ID被临时替换
        pass

    # 使用装饰器
    @context.with_request_id()
    def my_function():
        pass

    # 在子线程中保留上下文
    def worker():
        print(context.get_request_id())  # 自动继承父线程的上下文

    thread = context.run_in_thread(worker)
"""

import os
import sys
import uuid
import threading
import contextvars
import logging
from typing import Optional, Callable, Any, TypeVar, cast

_logger = logging.getLogger(__name__)

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])

# 上下文变量
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
_span_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="-")
_parent_span_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("parent_span_id", default="-")

# 配置引用
_config = None

# 上下文调试开关
_CONTEXT_DEBUG = os.environ.get('DATAMIND_CONTEXT_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """上下文内部调试输出"""
    if _CONTEXT_DEBUG:
        if args:
            print(f"[Context] {msg % args}", file=sys.stderr)
        else:
            print(f"[Context] {msg}", file=sys.stderr)


def set_config(config: Any) -> None:
    """设置配置引用"""
    global _config
    _config = config


# ==================== 线程上下文传递 ====================

def run_in_thread(target: Callable, *args, **kwargs) -> threading.Thread:
    """在子线程中运行函数，自动复制当前上下文

    参数:
        target: 目标函数
        *args: 位置参数
        **kwargs: 关键字参数

    返回:
        创建的线程对象

    示例:
        def worker():
            print(context.get_request_id())  # 自动继承父线程的上下文

        thread = context.run_in_thread(worker)
        thread.join()
    """
    ctx = contextvars.copy_context()

    def wrapper() -> None:
        for var, value in ctx.items():
            var.set(value)
        return target(*args, **kwargs)

    thread = threading.Thread(target=wrapper)
    _debug("创建上下文感知线程: %s", thread.name)
    return thread


def start_thread(target: Callable, *args, **kwargs) -> threading.Thread:
    """启动一个上下文感知的线程（run_in_thread 的别名）"""
    thread = run_in_thread(target, *args, **kwargs)
    thread.start()
    return thread


class ContextPreservingThread(threading.Thread):
    """自动保留上下文的线程类

    使用示例:
        thread = ContextPreservingThread(target=worker)
        thread.start()
    """

    def __init__(self, target: Optional[Callable] = None, *args, **kwargs):
        self._target = target
        self._ctx = contextvars.copy_context()
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        if self._target:
            self._ctx.run(self._target)


# ==================== Request ID 相关函数 ====================

def get_request_id() -> str:
    """获取当前请求ID"""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """设置当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set(request_id)
    _debug("设置请求ID: %s -> %s", old_id, request_id)


def has_request_id() -> bool:
    """检查是否有请求ID"""
    return _request_id_ctx.get() != "-"


def clear_request_id() -> None:
    """清除当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set("-")
    _debug("清除请求ID: %s -> -", old_id)


# ==================== Trace ID 相关函数 ====================

def get_trace_id() -> str:
    """获取当前 trace_id（链路追踪ID）"""
    return _trace_id_ctx.get()


def set_trace_id(trace_id: str) -> None:
    """设置当前 trace_id（链路追踪ID）"""
    old_id = _trace_id_ctx.get()
    _trace_id_ctx.set(trace_id)
    _debug("设置 trace_id: %s -> %s", old_id, trace_id)


def has_trace_id() -> bool:
    """检查是否有 trace_id"""
    return _trace_id_ctx.get() != "-"


def clear_trace_id() -> None:
    """清除当前 trace_id"""
    old_id = _trace_id_ctx.get()
    _trace_id_ctx.set("-")
    _debug("清除 trace_id: %s -> -", old_id)


# ==================== Span ID 相关函数 ====================

def get_span_id() -> str:
    """获取当前 span_id（调用层级ID）"""
    return _span_id_ctx.get()


def set_span_id(span_id: str) -> None:
    """设置当前 span_id（调用层级ID）"""
    old_id = _span_id_ctx.get()
    _span_id_ctx.set(span_id)
    _debug("设置 span_id: %s -> %s", old_id, span_id)


def has_span_id() -> bool:
    """检查是否有 span_id"""
    return _span_id_ctx.get() != "-"


def clear_span_id() -> None:
    """清除当前 span_id"""
    old_id = _span_id_ctx.get()
    _span_id_ctx.set("-")
    _debug("清除 span_id: %s -> -", old_id)


# ==================== Parent Span ID 相关函数 ====================

def get_parent_span_id() -> str:
    """获取当前父 span_id"""
    return _parent_span_id_ctx.get()


def set_parent_span_id(parent_span_id: str) -> None:
    """设置当前父 span_id"""
    old_id = _parent_span_id_ctx.get()
    _parent_span_id_ctx.set(parent_span_id)
    _debug("设置 parent_span_id: %s -> %s", old_id, parent_span_id)


def has_parent_span_id() -> bool:
    """检查是否有 parent_span_id"""
    return _parent_span_id_ctx.get() != "-"


def clear_parent_span_id() -> None:
    """清除当前 parent_span_id"""
    old_id = _parent_span_id_ctx.get()
    _parent_span_id_ctx.set("-")
    _debug("清除 parent_span_id: %s -> -", old_id)


# ==================== 辅助函数 ====================

def ensure_request(create_request: bool = True) -> None:
    """确保请求ID存在（入口调用）

    参数:
        create_request: 是否创建 request_id（如果不存在）
    """
    if create_request and _request_id_ctx.get() == "-":
        request_id = generate_request_id()
        set_request_id(request_id)
        _debug("自动创建请求ID: %s", request_id)


def ensure_trace(create_trace: bool = True, create_request: bool = True) -> None:
    """确保 trace 存在（入口调用）

    参数:
        create_trace: 是否创建 trace_id（如果不存在）
        create_request: 是否创建 request_id（如果不存在）
    """
    if create_trace and _trace_id_ctx.get() == "-":
        trace_id = generate_trace_id()
        set_trace_id(trace_id)
        _debug("自动创建 trace_id: %s", trace_id)

    if create_request and _request_id_ctx.get() == "-":
        request_id = generate_request_id()
        set_request_id(request_id)
        _debug("自动创建请求ID: %s", request_id)


def ensure_span(create_span: bool = True, create_parent_span: bool = False) -> None:
    """确保 span 存在（入口调用）

    参数:
        create_span: 是否创建 span_id（如果不存在）
        create_parent_span: 是否创建 parent_span_id（如果不存在）
    """
    if create_span and _span_id_ctx.get() == "-":
        span_id = generate_span_id()
        set_span_id(span_id)
        _debug("自动创建 span_id: %s", span_id)

    if create_parent_span and _parent_span_id_ctx.get() == "-":
        parent_span_id = generate_span_id()
        set_parent_span_id(parent_span_id)
        _debug("自动创建 parent_span_id: %s", parent_span_id)


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
        set_parent_span_id(parent_span_id)


def reset_context() -> None:
    """重置所有上下文变量（主要用于测试）"""
    _request_id_ctx.set("-")
    _trace_id_ctx.set("-")
    _span_id_ctx.set("-")
    _parent_span_id_ctx.set("-")
    _debug("重置所有上下文")


# ==================== 上下文管理器 ====================

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
        self.old_span = get_span_id()
        self.old_parent = get_parent_span_id()

        new_span = generate_span_id()
        set_span_id(new_span)

        if self.old_span != "-":
            set_parent_span_id(self.old_span)

        _debug("进入 span: %s (parent: %s, name: %s)",
               new_span, get_parent_span_id(), self.name)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.old_parent is not None:
            set_parent_span_id(self.old_parent)
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


# ==================== 装饰器 ====================

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


__all__ = [
    "get_request_id", "set_request_id", "clear_request_id", "has_request_id",
    "get_trace_id", "set_trace_id", "clear_trace_id", "has_trace_id",
    "get_span_id", "set_span_id", "clear_span_id", "has_span_id",
    "get_parent_span_id", "set_parent_span_id", "clear_parent_span_id", "has_parent_span_id",
    "ensure_request", "ensure_trace", "ensure_span",
    "generate_request_id", "generate_trace_id", "generate_span_id",
    "get_context", "set_context", "reset_context",
    "SpanContext", "RequestIdContext", "RequestContext",
    "with_request_id", "with_span",
    "run_in_thread", "start_thread", "ContextPreservingThread",
]