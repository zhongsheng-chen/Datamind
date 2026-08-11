# datamind/runtime/shadow.py

"""影子预测调度器

负责通过有界后台队列调度影子预测，
实现影子执行与主请求链路解耦。

核心功能：
  - start: 启动影子预测 Worker
  - submit: 提交影子预测任务
  - stop: 停止影子预测 Worker
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from datamind.runtime.executor import ExecutionPlan

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ShadowTask:
    """影子预测任务"""

    execution_id: str
    request_id: str
    decision_id: str
    plan: ExecutionPlan
    features: dict[str, Any]


class ShadowDispatcher:
    """有界影子预测调度器"""

    def __init__(
            self,
            *,
            handler: Callable[[ShadowTask], Awaitable[None]],
            enabled: bool,
            queue_size: int,
            worker_count: int,
            shutdown_timeout: float,
    ) -> None:
        """初始化影子预测调度器"""
        self._handler = handler
        self._enabled = enabled
        self._worker_count = worker_count
        self._shutdown_timeout = shutdown_timeout
        self._queue: asyncio.Queue[ShadowTask] = (
            asyncio.Queue(
                maxsize=queue_size
            )
        )
        self._workers: list[asyncio.Task[None]] = []

    @property
    def is_running(self) -> bool:
        """返回调度器是否正在运行"""
        return bool(self._workers)

    @property
    def pending_count(self) -> int:
        """返回等待执行的任务数量"""
        return self._queue.qsize()

    async def start(self) -> None:
        """启动影子预测 Worker"""
        if not self._enabled or self._workers:
            return

        self._workers = [
            asyncio.create_task(
                self._run_worker(),
                name=f"datamind-shadow-{index + 1}",
            )
            for index in range(self._worker_count)
        ]

    def submit(
            self,
            task: ShadowTask,
    ) -> bool:
        """提交影子预测任务，队列已满时立即拒绝"""
        if not self._enabled or not self._workers:
            return False

        try:
            self._queue.put_nowait(
                task
            )
        except asyncio.QueueFull:
            return False

        return True

    async def stop(self) -> None:
        """等待已接收任务完成并停止 Worker"""
        if not self._workers:
            return

        try:
            await asyncio.wait_for(
                self._queue.join(),
                timeout=self._shutdown_timeout,
            )
        except TimeoutError:
            logger.warning(
                "影子预测队列未在关闭期限内清空",
                pending=self._queue.qsize(),
            )

        workers = self._workers
        self._workers = []

        for worker in workers:
            worker.cancel()

        await asyncio.gather(
            *workers,
            return_exceptions=True,
        )

    async def _run_worker(self) -> None:
        """持续消费影子预测任务"""
        while True:
            task = await self._queue.get()

            try:
                handler_result = (
                    await asyncio.gather(
                        self._handler(
                            task
                        ),
                        return_exceptions=True,
                    )
                )[0]

                if isinstance(
                        handler_result,
                        asyncio.CancelledError,
                ):
                    raise handler_result

                if isinstance(
                        handler_result,
                        Exception,
                ):
                    logger.error(
                        "影子预测任务执行失败",
                        request_id=task.request_id,
                        deployment_id=(
                            task.plan.route.deployment_id
                        ),
                        error=(
                            str(handler_result)
                            or handler_result.__class__.__name__
                        ),
                        exc_info=(
                            handler_result.__class__,
                            handler_result,
                            handler_result.__traceback__,
                        ),
                    )
            finally:
                self._queue.task_done()
