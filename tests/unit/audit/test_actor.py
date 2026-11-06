"""审计操作人快照测试.

验证审计身份上下文的复制、隔离及对外序列化边界。

核心功能：
  - test_actor_snapshot_is_independent:
    验证快照不共享可变路径对象
  - test_actor_context_isolated_between_tasks:
    验证并发操作人的身份隔离
  - test_actor_excluded_from_authenticated_response:
    验证认证响应不暴露审计快照
"""

import asyncio
from typing import Any

import pytest

from datamind.audit.actor import (
    actor_snapshot,
    current_actor,
)
from datamind.auth.enums import UserStatus
from datamind.auth.schemas import AuthenticatedUser
from datamind.context import get_context


def test_actor_snapshot_is_independent() -> None:
    """验证快照复制嵌套路径，且不会进入普通日志上下文."""
    actor: dict[str, Any] = {
        "user_id": "usr_alice",
        "department_path": [{"name": "人力资源部"}],
    }
    token = current_actor.set(actor)

    try:
        snapshot = actor_snapshot()

        assert snapshot is not None

        actor["department_path"][0]["name"] = "人力资源管理部"

        assert snapshot["department_path"][0]["name"] == "人力资源部"
        assert "actor" not in get_context()
    finally:
        current_actor.reset(token)


@pytest.mark.asyncio
async def test_actor_context_isolated_between_tasks() -> None:
    """验证并发任务在等待后仍能读取各自的操作人身份."""

    async def observe(user_id: str) -> str:
        token = current_actor.set({"user_id": user_id})

        try:
            await asyncio.sleep(0)
            snapshot = actor_snapshot()

            assert snapshot is not None

            return snapshot["user_id"]
        finally:
            current_actor.reset(token)

    assert await asyncio.gather(
        observe("usr_alice"),
        observe("usr_bob"),
    ) == [
        "usr_alice",
        "usr_bob",
    ]
    assert actor_snapshot() is None


def test_actor_excluded_from_authenticated_response() -> None:
    """验证服务端身份快照不加入认证响应的 JSON 内容."""
    user = AuthenticatedUser(
        user_id="usr_alice",
        username="alice",
        status=UserStatus.ACTIVE,
        actor={"employee_number": "001234"},
    )

    assert "actor" not in user.model_dump()
    assert "001234" not in user.model_dump_json()
