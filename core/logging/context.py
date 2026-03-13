# core/logging/context.py
import contextvars

# 请求ID上下文变量
_request_id_ctx = contextvars.ContextVar("request_id", default="-")

def get_request_id() -> str:
    """获取当前请求ID"""
    return _request_id_ctx.get()

def set_request_id(request_id: str):
    """设置当前请求ID"""
    _request_id_ctx.set(request_id)