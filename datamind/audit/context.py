# datamind/audit/context.py

"""审计上下文

使用 contextvars 实现请求级别的审计上下文传递，支持异步和并发场景。

核心功能：
  - set_context: 设置审计上下文
  - get_context: 获取审计上下文
  - clear_context: 清除审计上下文
  - audit_context: 审计上下文管理器

使用示例：
  from datamind.audit.context import audit_context

  with audit_context(user_id="admin", ip="192.168.1.100"):
      # 所有审计记录自动带上 user_id 和 ip
      recorder.record(action="deploy", target_type="model", target_id="001")
"""

from contextvars import ContextVar
from contextlib import contextmanager
from typing import Dict, Any

_audit_ctx: ContextVar[Dict[str, Any]] = ContextVar("audit_ctx", default={})


def set_context(**kwargs) -> None:
    """设置审计上下文

    参数：
        **kwargs: 上下文字段（user_id, ip, trace_id 等）
    """
    ctx = _audit_ctx.get().copy()
    ctx.update(kwargs)
    _audit_ctx.set(ctx)


def get_context() -> Dict[str, Any]:
    """获取审计上下文

    返回：
        审计上下文字典
    """
    return _audit_ctx.get()


def clear_context() -> None:
    """清除审计上下文"""
    _audit_ctx.set({})


@contextmanager
def audit_context(**kwargs):
    """审计上下文管理器

    参数：
        **kwargs: 上下文字段

    使用示例：
        with audit_context(user_id="admin", ip="192.168.1.100"):
            recorder.record(...)
    """
    old = _audit_ctx.get()
    new = old.copy()
    new.update(kwargs)

    token = _audit_ctx.set(new)

    try:
        yield
    finally:
        _audit_ctx.reset(token)