# core/logging/debug.py

import threading
import sys

# 调试递归保护
_IN_DEBUG = threading.local()


def in_debug():
    """检查是否在调试中"""
    return getattr(_IN_DEBUG, 'value', False)


def set_debug(value: bool):
    """设置调试状态"""
    _IN_DEBUG.value = value


def debug_print(component: str, msg, *args):
    """统一的调试输出函数"""
    if in_debug():
        return

    set_debug(True)
    try:
        formatted_msg = f"[{component}] {msg}" % args if args else f"[{component}] {msg}"
        print(formatted_msg, file=sys.stderr)
    finally:
        set_debug(False)