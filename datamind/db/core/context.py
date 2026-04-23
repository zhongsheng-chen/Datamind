# datamind/db/core/context.py

"""数据库上下文

使用 contextvars 实现请求级别的数据库上下文传递。

核心功能：
  - set_context: 设置数据库上下文
  - get_context: 获取数据库上下文
  - clear_context: 清除数据库上下文

使用示例：
  from datamind.db.core.context import set_context, get_context

  set_context(user_id="admin", trace_id="trace-001")
  ctx = get_context()
"""

from contextvars import ContextVar
from typing import Dict, Any

_db_context: ContextVar[Dict[str, Any]] = ContextVar("db_context", default={})


def set_context(**kwargs) -> None:
    """设置数据库上下文

    参数：
        **kwargs: 上下文字段（user_id, trace_id, ip 等）
    """
    ctx = _db_context.get()
    ctx.update(kwargs)
    _db_context.set(ctx)


def get_context() -> Dict[str, Any]:
    """获取数据库上下文

    返回：
        上下文字典
    """
    return _db_context.get()


def clear_context() -> None:
    """清除数据库上下文"""
    _db_context.set({})