"""控制台事件仓储测试

验证事件游标查询、顺序回放、参数校验和过期事件清理。

核心功能：
  - test_get_latest_event_id:
    验证获取最新事件游标
  - test_list_events:
    验证按游标顺序查询事件
  - test_list_events_rejects_invalid_arguments:
    验证查询参数校验
  - test_delete_events_before:
    验证清理过期事件
"""

from datetime import (
    datetime,
    timezone,
)
from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy import Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Delete

from datamind.db.models.outbox import OutboxEvent
from datamind.db.repositories.outbox import OutboxRepository


CURRENT_TIME = datetime(
    2026,
    8,
    5,
    2,
    30,
    tzinfo=timezone.utc,
)


def create_repository(
        result: MagicMock,
) -> tuple[OutboxRepository, AsyncMock]:
    """创建控制台事件仓储及会话替身"""
    execute = AsyncMock(
        return_value=result
    )
    session_mock = MagicMock(
        spec=AsyncSession
    )
    session_mock.execute = execute
    session = cast(
        AsyncSession,
        cast(
            object,
            session_mock,
        ),
    )

    return OutboxRepository(session), execute


@pytest.mark.asyncio
async def test_get_latest_event_id() -> None:
    """测试获取最新事件游标"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = 42
    repository, _ = create_repository(
        result
    )

    event_id = await repository.get_latest_event_id()

    assert event_id == 42


@pytest.mark.asyncio
async def test_list_events() -> None:
    """测试按游标顺序查询事件"""
    events = [
        OutboxEvent(
            event_id=11,
            topic="models",
            resource_id="mdl_test",
            action="update",
        )
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = events
    repository, execute = create_repository(
        result
    )

    records = await repository.list_events(
        after_event_id=10,
        limit=20,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert records == events
    assert "outbox.event_id > 10" in sql
    assert "ORDER BY outbox.event_id ASC" in sql
    assert "LIMIT 20" in sql


@pytest.mark.parametrize(
    ("after_event_id", "limit", "message"),
    [
        (-1, 20, "after_event_id 必须大于等于 0"),
        (0, 0, "limit 必须在 1 到 1000 之间"),
        (0, 1001, "limit 必须在 1 到 1000 之间"),
    ],
)
@pytest.mark.asyncio
async def test_list_events_rejects_invalid_arguments(
        after_event_id: int,
        limit: int,
        message: str,
) -> None:
    """测试查询参数校验"""
    repository, execute = create_repository(
        MagicMock()
    )

    with pytest.raises(
            ValueError,
            match=message,
    ):
        await repository.list_events(
            after_event_id=after_event_id,
            limit=limit,
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_events_before() -> None:
    """测试清理过期事件"""
    result = MagicMock()
    repository, execute = create_repository(
        result
    )

    await repository.delete_events_before(
        CURRENT_TIME
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    assert isinstance(
        statement,
        Delete,
    )
    table = statement.table
    assert isinstance(
        table,
        Table,
    )
    assert table.name == "outbox"

    whereclause = statement.whereclause
    assert whereclause is not None
    sql = str(
        whereclause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "outbox.occurred_at <" in sql
