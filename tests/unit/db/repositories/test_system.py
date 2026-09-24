"""系统状态仓储测试.

验证系统状态读取、行锁定和初始化完成标记能力。

核心功能：
  - test_get_state_queries_system_id:
    验证按系统标识查询状态
  - test_get_state_supports_row_lock:
    验证初始化查询使用行锁
  - test_get_or_create_state:
    验证原子获取或创建系统状态
  - test_mark_initialized:
    验证标记系统完成初始化
"""

from datetime import (
    datetime,
    timezone,
)
from typing import (
    Any,
    cast,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from datamind.db.models.system import SystemState
from datamind.db.repositories.system import (
    SystemStateRepository,
)


CURRENT_TIME = datetime(
    2026,
    8,
    2,
    8,
    30,
    tzinfo=timezone.utc,
)


def create_repository(
        *,
        state: SystemState | None = None,
) -> tuple[
    SystemStateRepository,
    AsyncMock,
]:
    """创建系统状态仓储及异步会话替身."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = state
    execute = AsyncMock(
        return_value=result
    )
    session = MagicMock(
        spec=AsyncSession
    )
    session.execute = execute

    return (
        SystemStateRepository(
            cast(
                AsyncSession,
                session,
            )
        ),
        execute,
    )


def compile_statement(
        statement: Select[Any],
) -> str:
    """将查询语句编译为 PostgreSQL SQL."""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )


@pytest.mark.asyncio
async def test_get_state_queries_system_id() -> None:
    """测试按系统标识查询状态."""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )
    repository, execute = create_repository(
        state=state
    )

    result = await repository.get_state()

    call = execute.await_args
    assert call is not None
    statement = call.args[0]
    sql = compile_statement(
        statement
    )
    assert result is state
    assert "systems.system_id = 'datamind'" in sql
    assert "FOR UPDATE" not in sql


@pytest.mark.asyncio
async def test_get_state_supports_row_lock() -> None:
    """测试初始化查询使用行锁."""
    repository, execute = create_repository()

    await repository.get_state(
        for_update=True
    )

    call = execute.await_args
    assert call is not None
    statement = call.args[0]
    assert "FOR UPDATE" in compile_statement(
        statement
    )


@pytest.mark.asyncio
async def test_get_or_create_state() -> None:
    """测试原子创建并锁定系统状态."""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )
    repository, execute = create_repository(
        state=state
    )
    state_result = execute.return_value
    execute.side_effect = [
        MagicMock(),
        state_result,
    ]

    result = await repository.get_or_create_state()

    insert_call = execute.await_args_list[0]
    insert_sql = str(
        insert_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )
    select_call = execute.await_args_list[1]
    select_sql = compile_statement(
        select_call.args[0]
    )
    expected_insert = " ".join((
        "INSERT",
        "INTO",
        SystemState.__tablename__,
    ))
    assert result is state
    assert expected_insert in insert_sql
    assert "ON CONFLICT (system_id) DO NOTHING" in insert_sql
    assert "FOR UPDATE" in select_sql


def test_mark_initialized() -> None:
    """测试标记系统完成初始化."""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )

    result = SystemStateRepository.mark_initialized(
        state,
        initialized_at=CURRENT_TIME,
        initialized_by="system:bootstrap",
    )

    assert result is state
    assert state.initialized is True
    assert state.initialized_at == CURRENT_TIME
    assert state.initialized_by == "system:bootstrap"
