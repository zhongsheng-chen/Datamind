"""控制台实时事件.

监听 PostgreSQL 变更通知，并向控制台 SSE 连接广播可靠事件游标。
通知连接不可用时定期查询 Outbox，保证页面仍可恢复更新。

核心功能：
  - ConsoleEventBroker: 控制台事件通知代理

使用示例：
  from datamind.console.events import ConsoleEventBroker

  broker = ConsoleEventBroker()

  await broker.start()
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import asyncpg
import structlog
from sqlalchemy.engine import make_url

from datamind.db.core import (
    UnitOfWork,
    get_db_url,
)
from datamind.db.repositories import OutboxRepository


logger = structlog.get_logger(__name__)

_CHANNEL = "datamind_console_events"
_POLL_INTERVAL_SECONDS = 5
_RECONNECT_DELAY_SECONDS = 3
_RETENTION = timedelta(
    hours=24
)
_CLEANUP_INTERVAL = timedelta(
    hours=1
)


class ConsoleEventBroker:
    """控制台事件通知代理."""

    def __init__(self) -> None:
        """初始化事件通知代理."""
        self._subscribers: set[asyncio.Queue[int]] = set()
        self._task: asyncio.Task[None] | None = None
        self._start_lock = asyncio.Lock()
        self._wake_event = asyncio.Event()
        self._last_event_id: int | None = None
        self._last_cleanup_at: datetime | None = None

    async def start(self) -> None:
        """启动 PostgreSQL 通知监听任务."""
        async with self._start_lock:
            task = self._task

            if task is not None and not task.done():
                return

            self._task = asyncio.create_task(
                self._run(),
                name="datamind-console-events",
            )

    async def stop(self) -> None:
        """停止 PostgreSQL 通知监听任务."""
        async with self._start_lock:
            task = self._task
            self._task = None

        if task is None:
            return

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        self._last_event_id = None
        self._wake_event.clear()

    @asynccontextmanager
    async def subscribe(
            self,
    ) -> AsyncIterator[asyncio.Queue[int]]:
        """订阅控制台事件游标."""
        await self.start()
        queue: asyncio.Queue[int] = asyncio.Queue(
            maxsize=1
        )
        self._subscribers.add(
            queue
        )

        try:
            yield queue
        finally:
            self._subscribers.discard(
                queue
            )

    async def _run(self) -> None:
        """持续监听通知并在异常时自动重连."""
        dsn = self._get_notification_dsn()

        while True:
            try:
                if dsn is None:
                    await self._poll_forever()
                else:
                    await self._listen(
                        dsn
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "控制台实时通知连接异常",
                    error=str(exc),
                )
                await self._poll_safely()
                await asyncio.sleep(
                    _RECONNECT_DELAY_SECONDS
                )

    async def _listen(
            self,
            dsn: str,
    ) -> None:
        """监听 PostgreSQL 通知频道."""
        connection = await asyncpg.connect(
            dsn=dsn
        )
        listener = self._receive_notification

        try:
            await connection.add_listener(
                _CHANNEL,
                listener,
            )
            await self._initialize_cursor()

            while True:
                try:
                    await asyncio.wait_for(
                        self._wake_event.wait(),
                        timeout=_POLL_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    pass

                self._wake_event.clear()
                await self._poll_once()
        finally:
            try:
                await connection.remove_listener(
                    _CHANNEL,
                    listener,
                )
            finally:
                await connection.close()

    async def _poll_forever(self) -> None:
        """在非 PostgreSQL 环境定期读取事件."""
        await self._initialize_cursor()

        while True:
            await asyncio.sleep(
                _POLL_INTERVAL_SECONDS
            )
            await self._poll_once()

    async def _initialize_cursor(self) -> None:
        """从当前最新事件初始化监听游标."""
        if self._last_event_id is not None:
            return

        async with UnitOfWork() as uow:
            latest = await OutboxRepository(
                uow.session
            ).get_latest_event_id()

        self._last_event_id = latest or 0

    async def _poll_once(self) -> None:
        """读取新增事件并广播最新游标."""
        if self._last_event_id is None:
            await self._initialize_cursor()

        after_event_id = self._last_event_id or 0

        while True:
            async with UnitOfWork() as uow:
                events = await OutboxRepository(
                    uow.session
                ).list_events(
                    after_event_id=after_event_id,
                )

            if not events:
                break

            latest_event_id = int(
                events[-1].event_id
            )
            after_event_id = latest_event_id
            self._last_event_id = latest_event_id
            self._broadcast(
                latest_event_id
            )

            if len(events) < 200:
                break

        await self._cleanup_if_due()

    async def _poll_safely(self) -> None:
        """在重连期间尝试查询事件且不终止监听任务."""
        try:
            await self._poll_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "控制台事件回放暂不可用",
                error=str(exc),
            )

    async def _cleanup_if_due(self) -> None:
        """定期清理超过保留期的事件."""
        now = datetime.now(
            timezone.utc
        )

        if (
                self._last_cleanup_at is not None
                and now - self._last_cleanup_at
                < _CLEANUP_INTERVAL
        ):
            return

        async with UnitOfWork() as uow:
            await OutboxRepository(
                uow.session
            ).delete_events_before(
                now - _RETENTION
            )

        self._last_cleanup_at = now

    def _receive_notification(
            self,
            _connection: asyncpg.Connection,
            _process_id: int,
            _channel: str,
            payload: str,
    ) -> None:
        """接收 PostgreSQL 事件通知."""
        try:
            event_id = int(
                payload
            )
        except ValueError:
            self._wake_event.set()
            return

        self._broadcast(
            event_id
        )
        self._wake_event.set()

    def _broadcast(
            self,
            event_id: int,
    ) -> None:
        """向所有 SSE 订阅者广播最新游标."""
        for queue in tuple(
                self._subscribers
        ):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            queue.put_nowait(
                event_id
            )

    @staticmethod
    def _get_notification_dsn() -> str | None:
        """获取 asyncpg 通知连接地址."""
        url = make_url(
            get_db_url()
        )

        if url.get_backend_name() != "postgresql":
            return None

        return url.set(
            drivername="postgresql"
        ).render_as_string(
            hide_password=False
        )


event_broker = ConsoleEventBroker()
