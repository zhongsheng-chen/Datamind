"""上下文核心测试.

验证上下文的设置、获取、更新、清除和异步隔离。

核心功能：
  - test_set_context:
    验证设置并获取上下文
  - test_set_context_replaces_existing_context:
    验证重新设置上下文时替换原有内容
  - test_update_context_preserves_existing_values:
    验证更新上下文时保留未修改字段
  - test_update_context_overwrites_existing_value:
    验证更新上下文时覆盖指定字段
  - test_clear_context:
    验证清除当前上下文
  - test_set_context_without_arguments_clears_context:
    验证无参数设置上下文时清除原有内容
  - test_context_isolated_between_tasks:
    验证异步任务之间的上下文相互隔离
"""

import asyncio
from typing import Any

import pytest

from datamind.context.core import (
    clear_context,
    get_context,
    set_context,
    update_context,
)


def test_set_context() -> None:
    """测试设置上下文."""
    set_context(
        trace_id="0123456789abcdef0123456789abcdef",
        request_id="req_0123456789abcdef",
        source="http",
        user="admin",
    )

    assert get_context() == {
        "trace_id": "0123456789abcdef0123456789abcdef",
        "request_id": "req_0123456789abcdef",
        "source": "http",
        "user": "admin",
    }


def test_set_context_replaces_existing_context() -> None:
    """测试设置上下文时替换原有内容."""
    set_context(
        trace_id="0123456789abcdef0123456789abcdef",
        user="admin",
    )

    set_context(
        request_id="req_0123456789abcdef",
        source="cli",
    )

    assert get_context() == {
        "request_id": "req_0123456789abcdef",
        "source": "cli",
    }


def test_update_context_preserves_existing_values() -> None:
    """测试更新上下文时保留未修改字段."""
    set_context(
        trace_id="0123456789abcdef0123456789abcdef",
        request_id="req_0123456789abcdef",
    )

    update_context(
        user="admin",
        ip="192.168.1.100",
    )

    assert get_context() == {
        "trace_id": "0123456789abcdef0123456789abcdef",
        "request_id": "req_0123456789abcdef",
        "user": "admin",
        "ip": "192.168.1.100",
    }


def test_update_context_overwrites_existing_value() -> None:
    """测试更新上下文时覆盖指定字段."""
    set_context(
        source="http",
        user="guest",
    )

    update_context(
        user="admin",
    )

    assert get_context() == {
        "source": "http",
        "user": "admin",
    }


def test_clear_context() -> None:
    """测试清除上下文."""
    set_context(
        trace_id="0123456789abcdef0123456789abcdef",
        request_id="req_0123456789abcdef",
    )

    clear_context()

    assert get_context() == {}


def test_set_context_without_arguments_clears_context() -> None:
    """测试无参数设置上下文时清除原有内容."""
    set_context(
        user="admin",
    )

    set_context()

    assert get_context() == {}


@pytest.mark.asyncio
async def test_context_isolated_between_tasks() -> None:
    """测试异步任务之间的上下文相互隔离."""

    async def read_context(
            trace_id: str,
            user: str,
    ) -> dict[str, Any]:
        set_context(
            trace_id=trace_id,
            user=user,
        )

        await asyncio.sleep(0)

        return get_context()

    first, second = await asyncio.gather(
        read_context(
            "0123456789abcdef0123456789abcdef",
            "admin",
        ),
        read_context(
            "fedcba9876543210fedcba9876543210",
            "operator",
        ),
    )

    assert first == {
        "trace_id": "0123456789abcdef0123456789abcdef",
        "user": "admin",
    }
    assert second == {
        "trace_id": "fedcba9876543210fedcba9876543210",
        "user": "operator",
    }
    assert get_context() == {}
