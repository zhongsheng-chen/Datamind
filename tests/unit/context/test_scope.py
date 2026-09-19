"""上下文作用域测试

验证临时上下文的合并、覆盖、嵌套和退出恢复。

核心功能：
  - test_context_scope_sets_temporary_context:
    验证作用域内设置临时上下文
  - test_context_scope_merges_existing_context:
    验证作用域合并已有上下文
  - test_context_scope_overrides_existing_value:
    验证作用域覆盖已有字段
  - test_nested_context_scope_restores_each_level:
    验证嵌套作用域逐层恢复上下文
  - test_context_scope_restores_context_after_exception:
    验证发生异常后恢复原有上下文
  - test_context_scope_without_arguments_preserves_context:
    验证空作用域保持当前上下文
"""

import pytest

from datamind.context.core import (
    get_context,
    set_context,
)
from datamind.context.scope import context_scope


def test_context_scope_sets_temporary_context() -> None:
    """测试作用域内设置临时上下文"""
    with context_scope(
        trace_id="0123456789abcdef0123456789abcdef",
        user="admin",
    ):
        assert get_context() == {
            "trace_id": "0123456789abcdef0123456789abcdef",
            "user": "admin",
        }

    assert get_context() == {}


def test_context_scope_merges_existing_context() -> None:
    """测试作用域合并已有上下文"""
    set_context(
        trace_id="0123456789abcdef0123456789abcdef",
        request_id="req_0123456789abcdef",
    )

    with context_scope(
        user="admin",
        source="cli",
    ):
        assert get_context() == {
            "trace_id": "0123456789abcdef0123456789abcdef",
            "request_id": "req_0123456789abcdef",
            "user": "admin",
            "source": "cli",
        }

    assert get_context() == {
        "trace_id": "0123456789abcdef0123456789abcdef",
        "request_id": "req_0123456789abcdef",
    }


def test_context_scope_overrides_existing_value() -> None:
    """测试作用域覆盖已有字段"""
    set_context(
        user="guest",
        source="http",
    )

    with context_scope(
        user="admin",
    ):
        assert get_context() == {
            "user": "admin",
            "source": "http",
        }

    assert get_context() == {
        "user": "guest",
        "source": "http",
    }


def test_nested_context_scope_restores_each_level() -> None:
    """测试嵌套作用域逐层恢复上下文"""
    with context_scope(
        user="admin",
    ):
        assert get_context() == {
            "user": "admin",
        }

        with context_scope(
            trace_id="0123456789abcdef0123456789abcdef",
            source="task",
        ):
            assert get_context() == {
                "user": "admin",
                "trace_id": "0123456789abcdef0123456789abcdef",
                "source": "task",
            }

        assert get_context() == {
            "user": "admin",
        }

    assert get_context() == {}


def test_context_scope_restores_context_after_exception() -> None:
    """测试发生异常后恢复原有上下文"""
    set_context(
        request_id="req_0123456789abcdef",
        user="admin",
    )

    with pytest.raises(
        RuntimeError,
        match="处理失败",
    ):
        with context_scope(
            trace_id="0123456789abcdef0123456789abcdef",
            user="operator",
        ):
            raise RuntimeError(
                "处理失败"
            )

    assert get_context() == {
        "request_id": "req_0123456789abcdef",
        "user": "admin",
    }


def test_context_scope_without_arguments_preserves_context() -> None:
    """测试空作用域保持当前上下文"""
    set_context(
        source="http",
        hostname="client",
    )

    with context_scope():
        assert get_context() == {
            "source": "http",
            "hostname": "client",
        }

    assert get_context() == {
        "source": "http",
        "hostname": "client",
    }
