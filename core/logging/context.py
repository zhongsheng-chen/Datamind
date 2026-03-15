# core/logging/context.py

import contextvars
from core.logging.debug import debug_print

# 请求ID上下文变量
_request_id_ctx = contextvars.ContextVar("request_id", default="-")

# 配置引用（将在初始化时设置）
_config = None


def set_config(config):
    """设置配置引用"""
    global _config
    _config = config


def _debug(msg, *args):
    """调试输出"""
    if _config and _config.context_debug:
        debug_print("Context", msg, *args)


def get_request_id() -> str:
    """获取当前请求ID"""
    request_id = _request_id_ctx.get()
    _debug("获取请求ID: %s", request_id)
    return request_id


def set_request_id(request_id: str):
    """设置当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set(request_id)
    _debug("设置请求ID: %s -> %s", old_id, request_id)


def has_request_id() -> bool:
    """检查是否有请求ID"""
    has_id = _request_id_ctx.get() != "-"
    _debug("检查请求ID是否存在: %s", has_id)
    return has_id


def clear_request_id():
    """清除当前请求ID"""
    old_id = _request_id_ctx.get()
    _request_id_ctx.set("-")
    _debug("清除请求ID: %s -> -", old_id)


class RequestIdContext:
    """请求ID上下文管理器"""

    def __init__(self, request_id: str = None):
        self.request_id = request_id
        self.old_id = None

    def __enter__(self):
        self.old_id = get_request_id()
        if self.request_id:
            set_request_id(self.request_id)
        _debug("进入请求ID上下文: %s", get_request_id())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_request_id(self.old_id)
        _debug("退出请求ID上下文: %s", get_request_id())


def with_request_id(request_id: str = None):
    """装饰器：在函数执行期间设置请求ID"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            old_id = get_request_id()
            try:
                if request_id:
                    set_request_id(request_id)
                _debug("装饰器设置请求ID: %s", get_request_id())
                return func(*args, **kwargs)
            finally:
                set_request_id(old_id)
                _debug("装饰器恢复请求ID: %s", old_id)

        return wrapper

    return decorator