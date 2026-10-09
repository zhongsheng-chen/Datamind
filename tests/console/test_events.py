"""控制台实时事件代理测试.

验证事件代理的订阅、生命周期、事件轮询和通知连接行为。

核心功能：
  - test_subscribe_returns_isolated_queue:
    验证创建隔离订阅队列
  - test_start_and_stop_manage_background_task:
    验证后台任务生命周期
  - test_poll_once_replays_all_event_batches:
    验证事件批量回放
  - test_listen_closes_connection_when_cancelled:
    验证通知连接清理
  - test_stop_is_idempotent:
    验证未启动时可以安全停止
  - test_initialize_cursor_reads_latest_event_once:
    测试初始化游标只读取一次最新事件
  - test_cleanup_removes_expired_events_once_per_interval:
    测试过期事件清理受时间间隔限制
  - test_poll_safely_suppresses_replay_error:
    测试安全轮询吞掉普通回放异常
  - test_poll_safely_preserves_cancellation:
    测试安全轮询继续传播任务取消
  - test_receive_notification_broadcasts_latest_cursor:
    测试数据库通知广播最新事件游标
  - test_receive_notification_wakes_polling_for_invalid_payload:
    测试无效通知仍唤醒数据库轮询
  - test_run_polls_during_notification_reconnect:
    测试通知异常后轮询事件并重新连接
  - test_get_notification_dsn_supports_postgresql_only:
    测试通知连接地址仅支持 PostgreSQL
  - test_stream_events_starts_with_consistent_sync:
    测试首次连接从最新游标执行一致性同步
  - test_stream_events_filters_topics_by_permission:
    测试事件流只推送当前用户有权查看的主题
  - test_events_streams_only_granted_topics:
    测试事件接口仅建立有权限主题的事件流
  - test_stream_events_reports_expired_session:
    测试事件流定期校验并报告登录会话过期
  - test_stream_events_sends_heartbeat_for_valid_session:
    测试有效会话在空闲时接收 SSE 心跳
  - test_event_repository_helpers:
    测试事件游标范围和增量事件查询
  - test_event_query_waits_for_cleanup_when_cancelled:
    测试事件查询取消时等待数据库清理完成
  - test_event_cursor_and_sse_encoding_helpers:
    测试事件游标解析和 SSE 消息编码
"""

import asyncio
import importlib
from collections.abc import AsyncIterator, Coroutine
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
    call,
)

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from datamind.auth.schemas import AuthenticatedUser
from datamind.console.events import ConsoleEventBroker
from datamind.db.models.outbox import OutboxEvent
from tests.console._app_support import (
    FakeEventBroker,
    app_module,
    create_event_request,
    create_user,
    timeout_wait_for,
)


events_module = importlib.import_module("datamind.console.events")


class FakeUnitOfWork:
    """控制台事件测试工作单元."""

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
    """测试订阅返回独立且有界的事件队列."""
    start = AsyncMock()
    monkeypatch.setattr(
        ConsoleEventBroker,
        "start",
        start,
    )
    broker = ConsoleEventBroker()

    async with broker.subscribe() as queue:
        queue.put_nowait(21)

        assert queue.maxsize == 1
        assert queue.get_nowait() == 21

    start.assert_awaited_once_with()
    assert queue not in broker._subscribers


@pytest.mark.asyncio
async def test_start_and_stop_manage_background_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启动幂等且停止时清理后台状态."""
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
    """测试初始化游标只读取一次最新事件."""
    repository = MagicMock()
    repository.get_latest_event_id = AsyncMock(return_value=17)
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
    """测试轮询连续读取并广播全部事件批次."""
    first_batch = [SimpleNamespace(event_id=event_id) for event_id in range(1, 201)]
    second_batch = [SimpleNamespace(event_id=201)]
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
        call(after_event_id=0),
        call(after_event_id=200),
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
    """测试过期事件清理受时间间隔限制."""
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
    """测试安全轮询吞掉普通回放异常."""
    broker = ConsoleEventBroker()
    poll_once = AsyncMock(side_effect=RuntimeError("database unavailable"))
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
    """测试安全轮询继续传播任务取消."""
    broker = ConsoleEventBroker()
    monkeypatch.setattr(
        broker,
        "_poll_once",
        AsyncMock(side_effect=asyncio.CancelledError),
    )

    with pytest.raises(asyncio.CancelledError):
        await broker._poll_safely()


def test_receive_notification_broadcasts_latest_cursor() -> None:
    """测试数据库通知广播最新事件游标."""
    broker = ConsoleEventBroker()
    first_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    second_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    first_queue.put_nowait(7)
    broker._subscribers.update(
        {
            first_queue,
            second_queue,
        }
    )

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
    """测试无效通知仍唤醒数据库轮询."""
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
    """测试通知监听取消时移除监听器并关闭连接."""

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
        AsyncMock(return_value=connection),
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

    with pytest.raises(asyncio.CancelledError):
        await broker._listen("postgresql://localhost/datamind")

    initialize_cursor.assert_awaited_once_with()
    connection.add_listener.assert_awaited_once()
    connection.remove_listener.assert_awaited_once()
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_run_polls_during_notification_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通知异常后轮询事件并重新连接."""
    broker = ConsoleEventBroker()
    monkeypatch.setattr(
        broker,
        "_get_notification_dsn",
        lambda: "postgresql://localhost/datamind",
    )
    listen = AsyncMock(
        side_effect=[
            RuntimeError("connection lost"),
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

    with pytest.raises(asyncio.CancelledError):
        await broker._run()

    assert listen.await_count == 2
    poll_safely.assert_awaited_once_with()


def test_get_notification_dsn_supports_postgresql_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通知连接地址仅支持 PostgreSQL."""
    monkeypatch.setitem(
        vars(events_module),
        "get_db_url",
        lambda: "sqlite+aiosqlite:///datamind.db",
    )

    assert ConsoleEventBroker._get_notification_dsn() is None

    monkeypatch.setitem(
        vars(events_module),
        "get_db_url",
        lambda: "postgresql+asyncpg://user:secret@localhost/datamind",
    )

    assert ConsoleEventBroker._get_notification_dsn() == (
        "postgresql://user:secret@localhost/datamind"
    )


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    """测试未启动的事件代理可以安全停止."""
    broker = ConsoleEventBroker()

    await broker.stop()
    await broker.stop()


@pytest.mark.asyncio
async def test_stream_events_starts_with_consistent_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次连接从最新游标执行一致性同步."""

    async def get_event_window() -> tuple[int | None, int]:
        return None, 12

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    request = create_event_request()
    stream = app_module._stream_events(
        request=request,
        allowed_topics={"models"},
    )

    message = await anext(stream)
    await stream.aclose()

    assert "event: sync" in message
    assert "id: 12" in message
    assert 'data: {"topics":["models"]}' in message


@pytest.mark.asyncio
async def test_stream_events_filters_topics_by_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流只推送当前用户有权查看的主题."""
    events = [
        OutboxEvent(
            event_id=6,
            topic="models",
            action="update",
        ),
        OutboxEvent(
            event_id=7,
            topic="audits",
            action="insert",
        ),
    ]

    async def get_event_window() -> tuple[int, int]:
        return 1, 7

    async def get_events_after(
        _event_id: int,
    ) -> list[OutboxEvent]:
        return events

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    request = create_event_request("5")
    stream = app_module._stream_events(
        request=request,
        allowed_topics={"models"},
    )

    message = await anext(stream)
    await stream.aclose()

    assert "event: changed" in message
    assert "id: 7" in message
    assert '"topics":["models"]' in message
    assert '"changes":[{"topic":"models","action":"update"}]' in message


@pytest.mark.asyncio
async def test_events_streams_only_granted_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件接口仅建立有权限主题的事件流."""
    user = create_user()
    received_topics: set[str] | None = None

    class DashboardStub:
        """控制台权限测试服务."""

        @staticmethod
        def get_access(
            _permissions: list[str],
        ) -> dict[str, bool]:
            return {
                "models": True,
                "audits": False,
            }

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return user

    async def stream_events(
        *,
        request: Request,
        allowed_topics: set[str],
    ) -> AsyncIterator[str]:
        nonlocal received_topics
        assert request.url.path == "/api/events"
        received_topics = allowed_topics
        yield "event: sync\ndata: {}\n\n"

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        DashboardStub,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_stream_events",
        stream_events,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/events")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert received_topics == {"models"}


@pytest.mark.asyncio
async def test_stream_events_reports_expired_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流定期校验并报告登录会话过期."""

    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
        _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
        _request: object,
    ) -> None:
        return None

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request("1"),
        allowed_topics={"models"},
    )

    message = await anext(stream)
    await stream.aclose()

    assert "event: authentication" in message
    assert 'data: {"status":"expired"}' in message


@pytest.mark.asyncio
async def test_stream_events_sends_heartbeat_for_valid_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效会话在空闲时接收 SSE 心跳."""

    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
        _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request("1"),
        allowed_topics={"models"},
    )

    message = await anext(stream)
    await stream.aclose()

    assert message == ": keep-alive\n\n"


@pytest.mark.asyncio
async def test_event_repository_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件游标范围和增量事件查询."""
    event = OutboxEvent(
        event_id=8,
        topic="models",
        action="update",
    )
    repository = MagicMock()
    repository.get_oldest_event_id = AsyncMock(return_value=3)
    repository.get_latest_event_id = AsyncMock(return_value=8)
    repository.list_events = AsyncMock(return_value=[event])
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "OutboxRepository",
        lambda _session: repository,
    )

    window = await app_module._get_event_window()
    events = await app_module._get_events_after(7)

    assert window == (
        3,
        8,
    )
    assert events == [event]
    repository.list_events.assert_awaited_once_with(
        after_event_id=7,
        limit=200,
    )


@pytest.mark.asyncio
async def test_event_query_waits_for_cleanup_when_cancelled() -> None:
    """测试事件查询取消时等待数据库清理完成."""
    query_started = asyncio.Event()
    allow_query_completion = asyncio.Event()

    async def query() -> str:
        query_started.set()
        await allow_query_completion.wait()
        return "completed"

    task = asyncio.create_task(app_module._complete_event_query(query()))
    await query_started.wait()

    task.cancel()
    await asyncio.sleep(0)

    assert not task.done()

    allow_query_completion.set()

    with pytest.raises(asyncio.CancelledError):
        await task


def test_event_cursor_and_sse_encoding_helpers() -> None:
    """测试事件游标解析和 SSE 消息编码."""
    assert app_module._parse_event_cursor(None) is None
    assert app_module._parse_event_cursor("invalid") is None
    assert app_module._parse_event_cursor("-1") is None
    assert app_module._parse_event_cursor("0") == 0

    message = app_module._encode_sse(
        event="authentication",
        data={"status": "expired"},
    )

    assert message == 'event: authentication\ndata: {"status":"expired"}\n\n'
