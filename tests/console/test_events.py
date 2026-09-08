"""控制台实时事件代理测试

验证事件代理的订阅、生命周期、事件轮询和通知连接行为。

核心功能：
  - test_subscribe_returns_isolated_queue: 验证创建隔离订阅队列
  - test_start_and_stop_manage_background_task: 验证后台任务生命周期
  - test_poll_once_replays_all_event_batches: 验证事件批量回放
  - test_listen_closes_connection_when_cancelled: 验证通知连接清理
  - test_stop_is_idempotent: 验证未启动时可以安全停止
"""

import asyncio
import importlib
from collections.abc import Coroutine
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
    call,
)

import pytest

from datamind.console.events import ConsoleEventBroker


events_module = importlib.import_module(
    "datamind.console.events"
)


class FakeUnitOfWork:
    """控制台事件测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_subscribe_returns_isolated_queue(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试订阅返回独立且有界的事件队列"""
    start = AsyncMock()
    monkeypatch.setattr(
        ConsoleEventBroker,
        "start",
        start,
    )
    broker = ConsoleEventBroker()

    async with broker.subscribe() as queue:
        queue.put_nowait(
            21
        )

        assert queue.maxsize == 1
        assert queue.get_nowait() == 21

    start.assert_awaited_once_with()
    assert queue not in broker._subscribers


@pytest.mark.asyncio
async def test_start_and_stop_manage_background_task(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启动幂等且停止时清理后台状态"""
    broker = ConsoleEventBroker()
    started = asyncio.Event()

    async def run_forever() -> None:
        started.set()
        await asyncio.Future()

    monkeypatch.setattr(
        broker,
        "_run",
        run_forever,
    )

    await broker.start()
    await started.wait()
    task = broker._task
    await broker.start()

    assert broker._task is task

    broker._last_event_id = 9
    broker._wake_event.set()
    await broker.stop()

    assert task is not None
    assert task.cancelled()
    assert broker._task is None
    assert broker._last_event_id is None
    assert not broker._wake_event.is_set()


@pytest.mark.asyncio
async def test_initialize_cursor_reads_latest_event_once(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化游标只读取一次最新事件"""
    repository = MagicMock()
    repository.get_latest_event_id = AsyncMock(
        return_value=17
    )
    monkeypatch.setitem(
        vars(events_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(events_module),
        "OutboxRepository",
        lambda _session: repository,
    )
    broker = ConsoleEventBroker()

    await broker._initialize_cursor()
    await broker._initialize_cursor()

    assert broker._last_event_id == 17
    repository.get_latest_event_id.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_poll_once_replays_all_event_batches(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试轮询连续读取并广播全部事件批次"""
    first_batch = [
        SimpleNamespace(
            event_id=event_id
        )
        for event_id in range(1, 201)
    ]
    second_batch = [
        SimpleNamespace(
            event_id=201
        )
    ]
    repository = MagicMock()
    repository.list_events = AsyncMock(
        side_effect=[
            first_batch,
            second_batch,
        ]
    )
    monkeypatch.setitem(
        vars(events_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(events_module),
        "OutboxRepository",
        lambda _session: repository,
    )
    broker = ConsoleEventBroker()
    broker._last_event_id = 0
    cleanup = AsyncMock()
    broadcast = MagicMock()
    monkeypatch.setattr(
        broker,
        "_cleanup_if_due",
        cleanup,
    )
    monkeypatch.setattr(
        broker,
        "_broadcast",
        broadcast,
    )

    await broker._poll_once()

    assert broker._last_event_id == 201
    assert repository.list_events.await_args_list == [
        call(
            after_event_id=0
        ),
        call(
            after_event_id=200
        ),
    ]
    assert broadcast.call_args_list == [
        call(200),
        call(201),
    ]
    cleanup.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cleanup_removes_expired_events_once_per_interval(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试过期事件清理受时间间隔限制"""
    repository = MagicMock()
    repository.delete_events_before = AsyncMock()
    monkeypatch.setitem(
        vars(events_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(events_module),
        "OutboxRepository",
        lambda _session: repository,
    )
    broker = ConsoleEventBroker()

    await broker._cleanup_if_due()
    await broker._cleanup_if_due()

    repository.delete_events_before.assert_awaited_once()
    assert broker._last_cleanup_at is not None


@pytest.mark.asyncio
async def test_poll_safely_suppresses_replay_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试安全轮询吞掉普通回放异常"""
    broker = ConsoleEventBroker()
    poll_once = AsyncMock(
        side_effect=RuntimeError(
            "database unavailable"
        )
    )
    monkeypatch.setattr(
        broker,
        "_poll_once",
        poll_once,
    )

    await broker._poll_safely()

    poll_once.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_poll_safely_preserves_cancellation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试安全轮询继续传播任务取消"""
    broker = ConsoleEventBroker()
    monkeypatch.setattr(
        broker,
        "_poll_once",
        AsyncMock(
            side_effect=asyncio.CancelledError
        ),
    )

    with pytest.raises(
            asyncio.CancelledError
    ):
        await broker._poll_safely()


def test_receive_notification_broadcasts_latest_cursor() -> None:
    """测试数据库通知广播最新事件游标"""
    broker = ConsoleEventBroker()
    first_queue: asyncio.Queue[int] = asyncio.Queue(
        maxsize=1
    )
    second_queue: asyncio.Queue[int] = asyncio.Queue(
        maxsize=1
    )
    first_queue.put_nowait(
        7
    )
    broker._subscribers.update({
        first_queue,
        second_queue,
    })

    broker._receive_notification(
        MagicMock(),
        1,
        "datamind_console_events",
        "12",
    )

    assert first_queue.get_nowait() == 12
    assert second_queue.get_nowait() == 12
    assert broker._wake_event.is_set()


def test_receive_notification_wakes_polling_for_invalid_payload(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试无效通知仍唤醒数据库轮询"""
    broker = ConsoleEventBroker()
    broadcast = MagicMock()
    monkeypatch.setattr(
        broker,
        "_broadcast",
        broadcast,
    )

    broker._receive_notification(
        MagicMock(),
        1,
        "datamind_console_events",
        "invalid",
    )

    broadcast.assert_not_called()
    assert broker._wake_event.is_set()


@pytest.mark.asyncio
async def test_listen_closes_connection_when_cancelled(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通知监听取消时移除监听器并关闭连接"""
    async def cancel_wait_for(
            awaitable: Coroutine[object, object, object],
            *,
            timeout: float,
    ) -> None:
        assert timeout > 0
        awaitable.close()
        raise asyncio.CancelledError

    connection = MagicMock()
    connection.add_listener = AsyncMock()
    connection.remove_listener = AsyncMock()
    connection.close = AsyncMock()
    monkeypatch.setitem(
        vars(events_module.asyncpg),
        "connect",
        AsyncMock(
            return_value=connection
        ),
    )
    monkeypatch.setitem(
        vars(events_module.asyncio),
        "wait_for",
        cancel_wait_for,
    )
    broker = ConsoleEventBroker()
    initialize_cursor = AsyncMock()
    monkeypatch.setattr(
        broker,
        "_initialize_cursor",
        initialize_cursor,
    )

    with pytest.raises(
            asyncio.CancelledError
    ):
        await broker._listen(
            "postgresql://localhost/datamind"
        )

    initialize_cursor.assert_awaited_once_with()
    connection.add_listener.assert_awaited_once()
    connection.remove_listener.assert_awaited_once()
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_run_polls_during_notification_reconnect(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通知异常后轮询事件并重新连接"""
    broker = ConsoleEventBroker()
    monkeypatch.setattr(
        broker,
        "_get_notification_dsn",
        lambda: "postgresql://localhost/datamind",
    )
    listen = AsyncMock(
        side_effect=[
            RuntimeError(
                "connection lost"
            ),
            asyncio.CancelledError,
        ]
    )
    poll_safely = AsyncMock()
    monkeypatch.setattr(
        broker,
        "_listen",
        listen,
    )
    monkeypatch.setattr(
        broker,
        "_poll_safely",
        poll_safely,
    )
    monkeypatch.setitem(
        vars(events_module.asyncio),
        "sleep",
        AsyncMock(),
    )

    with pytest.raises(
            asyncio.CancelledError
    ):
        await broker._run()

    assert listen.await_count == 2
    poll_safely.assert_awaited_once_with()


def test_get_notification_dsn_supports_postgresql_only(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通知连接地址仅支持 PostgreSQL"""
    monkeypatch.setitem(
        vars(events_module),
        "get_db_url",
        lambda: "sqlite+aiosqlite:///datamind.db",
    )

    assert ConsoleEventBroker._get_notification_dsn() is None

    monkeypatch.setitem(
        vars(events_module),
        "get_db_url",
        lambda: (
            "postgresql+asyncpg://"
            "user:secret@localhost/datamind"
        ),
    )

    assert ConsoleEventBroker._get_notification_dsn() == (
        "postgresql://user:secret@localhost/datamind"
    )


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    """测试未启动的事件代理可以安全停止"""
    broker = ConsoleEventBroker()

    await broker.stop()
    await broker.stop()
