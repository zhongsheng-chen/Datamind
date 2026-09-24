"""批量任务发布与执行链路集成测试.

使用真实 Redis broker 和 Datamind Celery 应用，验证批量任务的发布、
消费、重试以及持久化状态转换。

核心功能：
  - test_publisher_worker_persists_execution_and_ignores_duplicate_delivery:
    验证正常任务和重复投递的幂等状态
  - test_failed_batch_can_be_retried_through_datamind_publisher:
    验证失败任务通过业务服务重试并形成新的 Attempt
  - test_batch_chunk_retries_then_persists_success:
    验证 Datamind 分片任务自动重试后持久化成功状态
  - test_batch_chunk_persists_failure_after_max_retries:
    验证 Datamind 分片任务耗尽重试后持久化失败状态
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any
import uuid

import pytest
from celery.contrib.testing.worker import start_worker
from kombu import Queue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

import datamind.runtime.task_queue.tasks as tasks_module
from datamind.constants import Framework, ModelType, TaskType
from datamind.db.core import UnitOfWork
from datamind.db.models import Attempt, Batch, Execution, Shard
from datamind.db.repositories import (
    AttemptRepository,
    BatchRepository,
    ExecutionRepository,
    MetadataRepository,
    ShardRepository,
)
from datamind.models.enums import ExecutionStatus, ExecutionType
from datamind.runtime.task_queue.app import celery_app
from datamind.runtime.task_queue.publisher import TaskPublisher
from datamind.services.batch import BatchLifecycleService


pytestmark = pytest.mark.integration


class DatabaseRuntimeWorkerHarness:
    """在真实 Celery 线程中驱动 Datamind 持久化边界."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.fail_once: set[str] = set()
        self.chunk_calls: dict[str, int] = {}
        self.chunk_failures_remaining: dict[str, int] = {}
        self.chunks_that_always_fail: set[str] = set()

    def prepare_batch(
        self,
        *,
        batch_id: str,
        task_id: str,
        worker_id: str | None = None,
    ) -> int:
        """启动批次并在真实数据库中写入一次确定性执行结果."""
        return self._submit(
            self._prepare_batch(
                batch_id=batch_id,
                task_id=task_id,
                worker_id=worker_id,
            )
        )

    def mark_batch_failed(self, *, batch_id: str, error: str) -> None:
        """持久化 Celery 入口捕获的批次失败."""
        self._submit(self._mark_batch_failed(batch_id=batch_id, error=error))

    def register_batch_shards(
        self,
        *,
        batch_id: str,
        shards: list[dict[str, object]],
    ) -> None:
        """防御性拒绝本测试不应产生的分片."""
        raise AssertionError(f"unexpected shards for {batch_id}: {shards}")

    def execute_batch_chunk(
        self,
        *,
        batch_id: str,
        shard_id: str,
        start_index: int,
        end_index: int,
        worker_id: str | None = None,
    ) -> None:
        """执行确定性分片，并保留真实 Repository 状态迁移."""
        self._submit(
            self._execute_batch_chunk(
                batch_id=batch_id,
                shard_id=shard_id,
                start_index=start_index,
                end_index=end_index,
                worker_id=worker_id,
            )
        )

    def mark_batch_chunk_retrying(self, *, shard_id: str, error: str) -> None:
        """通过真实 ShardRepository 记录等待重试状态."""
        self._submit(self._mark_batch_chunk_retrying(shard_id=shard_id, error=error))

    def mark_batch_chunk_failed(
        self,
        *,
        batch_id: str,
        shard_id: str,
        start_index: int,
        end_index: int,
        error: str,
    ) -> None:
        """通过真实 Repository 记录重试耗尽后的终态."""
        del start_index, end_index
        self._submit(
            self._mark_batch_chunk_failed(
                batch_id=batch_id,
                shard_id=shard_id,
                error=error,
            )
        )

    def _submit(self, coroutine: Coroutine[Any, Any, Any]) -> Any:
        """将 Worker 线程中的数据库操作提交回 pytest 事件循环."""
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        return future.result(timeout=20)

    async def _prepare_batch(
        self,
        *,
        batch_id: str,
        task_id: str,
        worker_id: str | None,
    ) -> int:
        """执行真实 Batch、Attempt 与 Execution 仓储状态迁移."""
        async with UnitOfWork() as uow:
            batch_repository = BatchRepository(uow.session)
            batch = await batch_repository.start(
                batch_id=batch_id,
                task_id=task_id,
            )

            if batch is None:
                return 0

            await AttemptRepository(uow.session).mark_started(
                batch_id=batch_id,
                task_id=task_id,
                attempt_number=batch.attempt_count,
                worker_id=worker_id,
            )

        if batch_id in self.fail_once:
            self.fail_once.remove(batch_id)
            raise RuntimeError("transient integration failure")

        execution_id = f"exe_{uuid.uuid4().hex}"
        decision_id = f"dcs_{uuid.uuid4().hex}"

        async with UnitOfWork() as uow:
            execution_repository = ExecutionRepository(uow.session)
            execution = execution_repository.create_execution(
                execution_id=execution_id,
                decision_id=decision_id,
                execution_type=ExecutionType.PRIMARY,
                status=ExecutionStatus.QUEUED,
                model_id=batch.model_id or "mdl_integration",
                version_id="ver_integration",
                deployment_id=None,
            )
            execution_repository.mark_running(execution)
            execution_repository.mark_success(
                execution,
                prediction={"prediction": 1},
                probability=0.9,
            )

            await BatchRepository(uow.session).mark_succeeded(
                batch_id=batch_id,
                result={
                    "success": True,
                    "count": 1,
                    "predictions": [{"prediction": 1}],
                },
            )
            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status="succeeded",
            )

        return 0

    async def _execute_batch_chunk(
        self,
        *,
        batch_id: str,
        shard_id: str,
        start_index: int,
        end_index: int,
        worker_id: str | None,
    ) -> None:
        """执行会按测试配置失败或成功的持久化分片."""
        assert (start_index, end_index) == (0, 1)
        self.chunk_calls[shard_id] = self.chunk_calls.get(shard_id, 0) + 1

        async with UnitOfWork() as uow:
            await ShardRepository(uow.session).mark_started(
                shard_id=shard_id,
                worker_id=worker_id,
            )

        failures_remaining = self.chunk_failures_remaining.get(shard_id, 0)
        if shard_id in self.chunks_that_always_fail or failures_remaining > 0:
            self.chunk_failures_remaining[shard_id] = max(
                failures_remaining - 1,
                0,
            )
            raise RuntimeError("persistent chunk integration failure")

        async with UnitOfWork() as uow:
            batch_repository = BatchRepository(uow.session)
            batch = await batch_repository.get_batch(batch_id)
            assert batch is not None

            execution_repository = ExecutionRepository(uow.session)
            execution = execution_repository.create_execution(
                execution_id=f"exe_{uuid.uuid4().hex}",
                decision_id=f"dcs_{uuid.uuid4().hex}",
                execution_type=ExecutionType.PRIMARY,
                status=ExecutionStatus.QUEUED,
                model_id=batch.model_id or "mdl_integration",
                version_id="ver_integration",
                deployment_id=None,
            )
            execution_repository.mark_running(execution)
            execution_repository.mark_success(
                execution,
                prediction={"prediction": 1},
                probability=0.9,
            )

            await ShardRepository(uow.session).mark_finished(
                shard_id=shard_id,
                status="succeeded",
            )
            await batch_repository.mark_succeeded(
                batch_id=batch_id,
                result={
                    "success": True,
                    "count": 1,
                    "predictions": [{"prediction": 1}],
                },
            )
            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status="succeeded",
            )

    @staticmethod
    async def _mark_batch_failed(*, batch_id: str, error: str) -> None:
        """将失败批次和当前 Attempt 一并置为终态."""
        async with UnitOfWork() as uow:
            await BatchRepository(uow.session).mark_failed(
                batch_id=batch_id,
                error=error,
                result={
                    "success": False,
                    "count": 0,
                    "predictions": [],
                },
            )
            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status="failed",
                error=error,
            )

    @staticmethod
    async def _mark_batch_chunk_retrying(*, shard_id: str, error: str) -> None:
        """持久化分片等待 Celery 重试状态."""
        async with UnitOfWork() as uow:
            await ShardRepository(uow.session).mark_retrying(
                shard_id=shard_id,
                error=error,
            )

    @staticmethod
    async def _mark_batch_chunk_failed(
        *,
        batch_id: str,
        shard_id: str,
        error: str,
    ) -> None:
        """持久化分片、批次和 Attempt 的失败终态."""
        async with UnitOfWork() as uow:
            await ShardRepository(uow.session).mark_finished(
                shard_id=shard_id,
                status="failed",
                error=error,
            )
            await BatchRepository(uow.session).mark_failed(
                batch_id=batch_id,
                error=error,
                result={
                    "success": False,
                    "count": 0,
                    "predictions": [],
                },
            )
            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status="failed",
                error=error,
            )


def queue_settings(redis_url: str, queue: str) -> SimpleNamespace:
    """构造只覆盖任务队列边界的隔离配置."""
    return SimpleNamespace(
        broker_url=redis_url,
        batch_queue=queue,
        shadow_queue=f"{queue}.shadow",
        max_retries=1,
        batch_chunk_size=20,
        retry_backoff_seconds=1,
        visibility_timeout_seconds=60,
    )


async def create_batch(batch_id: str, task_id: str) -> None:
    """通过 Datamind Repository 创建待发布批次与首次 Attempt."""
    async with UnitOfWork() as uow:
        MetadataRepository(uow.session).create_model(
            model_id=f"mdl_{batch_id[4:]}",
            name=f"queue-{batch_id}",
            model_type=ModelType.LOGISTIC_REGRESSION,
            task_type=TaskType.CLASSIFICATION,
            framework=Framework.SKLEARN,
        )
        BatchRepository(uow.session).create_batch(
            batch_id=batch_id,
            task_id=task_id,
            model_id=f"mdl_{batch_id[4:]}",
            model_name=f"queue-{batch_id}",
            deployment_id=None,
            environment="testing",
            payload={
                "model_name": f"queue-{batch_id}",
                "instances": [{"features": {"value": 1.0}}],
            },
            total_count=1,
            source="integration",
            user="integration-test",
            ip="127.0.0.1",
        )
        AttemptRepository(uow.session).create_attempt(
            batch_id=batch_id,
            task_id=task_id,
            attempt_number=1,
        )


async def create_running_shard(
    *,
    batch_id: str,
    task_id: str,
    shard_id: str,
    shard_task_id: str,
) -> None:
    """启动批次、Attempt，并创建一个真实待执行分片."""
    async with UnitOfWork() as uow:
        batch = await BatchRepository(uow.session).start(
            batch_id=batch_id,
            task_id=task_id,
        )
        assert batch is not None

        attempt = await AttemptRepository(uow.session).mark_started(
            batch_id=batch_id,
            task_id=task_id,
            attempt_number=batch.attempt_count,
            worker_id="integration-coordinator",
        )
        assert attempt is not None

        ShardRepository(uow.session).create_shard(
            shard_id=shard_id,
            attempt_id=attempt.attempt_id,
            batch_id=batch_id,
            task_id=shard_task_id,
            start_index=0,
            end_index=1,
        )


async def wait_for_batch_status(
    batch_id: str,
    expected: str,
    *,
    timeout: float = 20,
) -> None:
    """轮询真实数据库直至 Worker 提交目标批次状态."""
    deadline = asyncio.get_running_loop().time() + timeout

    while asyncio.get_running_loop().time() < deadline:
        async with UnitOfWork() as uow:
            batch = await BatchRepository(uow.session).get_batch(batch_id)

        if batch is not None and batch.status == expected:
            return

        await asyncio.sleep(0.1)

    pytest.fail(f"batch {batch_id} did not reach {expected}")


async def wait_for_shard_status(
    shard_id: str,
    expected: str,
    *,
    timeout: float = 20,
) -> None:
    """轮询真实数据库直至分片进入目标状态."""
    deadline = asyncio.get_running_loop().time() + timeout

    while asyncio.get_running_loop().time() < deadline:
        async with UnitOfWork() as uow:
            shard = await uow.session.scalar(
                select(Shard).where(Shard.shard_id == shard_id)
            )

        if isinstance(shard, Shard) and shard.status == expected:
            return

        await asyncio.sleep(0.1)

    pytest.fail(f"shard {shard_id} did not reach {expected}")


@pytest.fixture
def configured_datamind_worker(
    redis_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, DatabaseRuntimeWorkerHarness]:
    """配置使用真实 Redis 隔离队列的 Datamind Celery Worker."""
    queue = f"datamind.integration.{uuid.uuid4().hex}"
    settings = queue_settings(redis_url, queue)
    loop = asyncio.get_event_loop()
    worker = DatabaseRuntimeWorkerHarness(loop)

    monkeypatch.setattr(
        "datamind.runtime.task_queue.publisher.get_task_queue_config",
        lambda: settings,
    )
    monkeypatch.setattr(
        "datamind.runtime.task_queue.tasks.get_task_queue_config",
        lambda: settings,
    )
    monkeypatch.setattr(
        "datamind.runtime.task_queue.tasks.get_runtime_task_worker",
        lambda: worker,
    )

    celery_app.conf.broker_url = redis_url
    celery_app.conf.task_queues = (Queue(queue),)
    celery_app.conf.task_routes = {
        tasks_module.execute_batch.name: {"queue": queue},
        tasks_module.execute_batch_chunk.name: {"queue": queue},
    }

    return queue, worker


@pytest.mark.asyncio
async def test_publisher_worker_persists_execution_and_ignores_duplicate_delivery(
    datamind_database: AsyncEngine,
    configured_datamind_worker: tuple[str, DatabaseRuntimeWorkerHarness],
) -> None:
    """测试正常发布落库且重复投递不产生第二次执行."""
    del datamind_database
    queue, _worker = configured_datamind_worker
    batch_id = f"bat_{uuid.uuid4().hex}"
    task_id = f"tsk_{uuid.uuid4().hex}"
    await create_batch(batch_id, task_id)

    with start_worker(
        celery_app,
        perform_ping_check=False,
        concurrency=1,
        pool="solo",
        queues=[queue],
    ):
        TaskPublisher().submit_batch(batch_id=batch_id, task_id=task_id)
        await wait_for_batch_status(batch_id, "succeeded")

        TaskPublisher().submit_batch(
            batch_id=batch_id,
            task_id=f"tsk_{uuid.uuid4().hex}",
        )
        await asyncio.sleep(0.5)

    async with UnitOfWork() as uow:
        attempt_count = await uow.session.scalar(
            select(func.count(Attempt.id)).where(Attempt.batch_id == batch_id)
        )
        execution_count = await uow.session.scalar(
            select(func.count(Execution.id)).where(
                Execution.model_id == f"mdl_{batch_id[4:]}"
            )
        )

    assert attempt_count == 1
    assert execution_count == 1


@pytest.mark.asyncio
async def test_failed_batch_can_be_retried_through_datamind_publisher(
    datamind_database: AsyncEngine,
    configured_datamind_worker: tuple[str, DatabaseRuntimeWorkerHarness],
) -> None:
    """测试失败批次经业务服务重试后产生第二次成功 Attempt."""
    del datamind_database
    queue, worker = configured_datamind_worker
    batch_id = f"bat_{uuid.uuid4().hex}"
    task_id = f"tsk_{uuid.uuid4().hex}"
    await create_batch(batch_id, task_id)
    worker.fail_once.add(batch_id)

    with start_worker(
        celery_app,
        perform_ping_check=False,
        concurrency=1,
        pool="solo",
        queues=[queue],
    ):
        TaskPublisher().submit_batch(batch_id=batch_id, task_id=task_id)
        await wait_for_batch_status(batch_id, "failed")

        await BatchLifecycleService().retry(batch_id=batch_id)
        await wait_for_batch_status(batch_id, "succeeded")

    async with UnitOfWork() as uow:
        attempts = list(
            (
                await uow.session.scalars(
                    select(Attempt)
                    .where(Attempt.batch_id == batch_id)
                    .order_by(Attempt.attempt_number)
                )
            ).all()
        )

    assert [attempt.attempt_number for attempt in attempts] == [1, 2]
    assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]


@pytest.mark.asyncio
async def test_batch_chunk_retries_then_persists_success(
    datamind_database: AsyncEngine,
    configured_datamind_worker: tuple[str, DatabaseRuntimeWorkerHarness],
) -> None:
    """测试 Datamind 分片任务一次失败后自动重试并持久化成功."""
    del datamind_database
    queue, worker = configured_datamind_worker
    batch_id = f"bat_{uuid.uuid4().hex}"
    task_id = f"tsk_{uuid.uuid4().hex}"
    shard_id = f"shd_{uuid.uuid4().hex}"
    shard_task_id = f"tsk_{uuid.uuid4().hex}"

    await create_batch(batch_id, task_id)
    await create_running_shard(
        batch_id=batch_id,
        task_id=task_id,
        shard_id=shard_id,
        shard_task_id=shard_task_id,
    )
    worker.chunk_failures_remaining[shard_id] = 1

    with start_worker(
        celery_app,
        perform_ping_check=False,
        concurrency=1,
        pool="solo",
        queues=[queue],
    ):
        TaskPublisher().submit_batch_chunk(
            batch_id=batch_id,
            shard_id=shard_id,
            task_id=shard_task_id,
            start_index=0,
            end_index=1,
        )
        await wait_for_shard_status(shard_id, "succeeded")

    async with UnitOfWork() as uow:
        attempt = await AttemptRepository(uow.session).get_latest_attempt(batch_id)
        execution_count = await uow.session.scalar(
            select(func.count(Execution.id)).where(
                Execution.model_id == f"mdl_{batch_id[4:]}"
            )
        )

    assert worker.chunk_calls[shard_id] == 2
    assert attempt is not None
    assert attempt.status == "succeeded"
    assert execution_count == 1


@pytest.mark.asyncio
async def test_batch_chunk_persists_failure_after_max_retries(
    datamind_database: AsyncEngine,
    configured_datamind_worker: tuple[str, DatabaseRuntimeWorkerHarness],
) -> None:
    """测试 Datamind 分片任务耗尽重试后持久化完整失败状态."""
    del datamind_database
    queue, worker = configured_datamind_worker
    batch_id = f"bat_{uuid.uuid4().hex}"
    task_id = f"tsk_{uuid.uuid4().hex}"
    shard_id = f"shd_{uuid.uuid4().hex}"
    shard_task_id = f"tsk_{uuid.uuid4().hex}"

    await create_batch(batch_id, task_id)
    await create_running_shard(
        batch_id=batch_id,
        task_id=task_id,
        shard_id=shard_id,
        shard_task_id=shard_task_id,
    )
    worker.chunks_that_always_fail.add(shard_id)

    with start_worker(
        celery_app,
        perform_ping_check=False,
        concurrency=1,
        pool="solo",
        queues=[queue],
    ):
        TaskPublisher().submit_batch_chunk(
            batch_id=batch_id,
            shard_id=shard_id,
            task_id=shard_task_id,
            start_index=0,
            end_index=1,
        )
        await wait_for_shard_status(shard_id, "failed")

    async with UnitOfWork() as uow:
        batch = await uow.session.scalar(
            select(Batch).where(Batch.batch_id == batch_id)
        )
        attempt = await AttemptRepository(uow.session).get_latest_attempt(batch_id)
        execution_count = await uow.session.scalar(
            select(func.count(Execution.id)).where(
                Execution.model_id == f"mdl_{batch_id[4:]}"
            )
        )

    assert worker.chunk_calls[shard_id] == 2
    assert isinstance(batch, Batch)
    assert batch.status == "failed"
    assert isinstance(attempt, Attempt)
    assert attempt.status == "failed"
    assert execution_count == 0
