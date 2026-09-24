"""预测批次仓储测试.

验证预测批次的创建、启动、取消、重试和部分成功状态迁移。

核心功能：
  - test_create_batch:
    验证创建等待执行的批次
  - test_start_matches_current_task:
    验证当前 Celery 任务启动等待批次
  - test_start_resumes_retrying_batch:
    验证当前 Celery 任务恢复等待自动重试的批次
  - test_start_ignores_stale_task:
    验证过期 Celery 任务不能启动批次
  - test_request_cancel_running_batch:
    验证运行中批次进入取消流程
  - test_retry_assigns_new_task_id:
    验证批次重试分配新任务 ID
  - test_mark_retrying_preserves_task_id:
    验证自动重试保留任务 ID 和执行进度
  - test_mark_partially_succeeded:
    验证批次记录部分成功状态
  - test_retry_partially_succeeded_batch:
    验证部分成功批次可以重试
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.models.batches import Batch
from datamind.db.repositories.batch import BatchRepository


def create_repository(
        batch: Batch | None = None,
) -> tuple[BatchRepository, MagicMock]:
    """创建使用会话替身的批次仓储."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = batch
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    repository = BatchRepository(
        cast(AsyncSession, cast(object, session))
    )
    return repository, session


def create_batch(**overrides: object) -> Batch:
    """创建批次记录测试对象."""
    values = {
        "batch_id": "bat_test",
        "task_id": "tsk_test",
        "model_name": "scorecard",
        "environment": "testing",
        "payload": {
            "model_name": "scorecard",
            "instances": [{"features": {"age": 35}}],
        },
        "total_count": 1,
        "completed_count": 0,
        "succeeded_count": 0,
        "failed_count": 0,
        "attempt_count": 0,
        "status": "queued",
    }
    values.update(overrides)
    return Batch(**values)


def test_create_batch() -> None:
    """测试创建等待执行的批次."""
    repository, session = create_repository()

    batch = repository.create_batch(
        batch_id="bat_test",
        task_id="tsk_test",
        model_id="mdl_test",
        model_name="scorecard",
        deployment_id=None,
        environment="testing",
        payload={"model_name": "scorecard", "instances": []},
        total_count=2,
        source="http",
        user="admin",
        ip="127.0.0.1",
    )

    assert batch.status == "queued"
    assert batch.batch_id == "bat_test"
    assert batch.task_id == "tsk_test"
    assert batch.model_id == "mdl_test"
    assert batch.completed_count == 0
    assert batch.succeeded_count == 0
    assert batch.failed_count == 0
    assert batch.attempt_count == 0
    session.add.assert_called_once_with(batch)


@pytest.mark.asyncio
async def test_start_matches_current_task() -> None:
    """测试只有当前 Celery 任务能够启动等待批次."""
    batch = create_batch()
    repository, _ = create_repository(batch)

    started = await repository.start(
        batch_id="bat_test",
        task_id="tsk_test",
    )

    assert started is batch
    assert batch.status == "running"
    assert batch.attempt_count == 1
    assert batch.started_at is not None


@pytest.mark.asyncio
async def test_start_resumes_retrying_batch() -> None:
    """测试当前 Celery 任务能够恢复等待重试的批次."""
    batch = create_batch(status="retrying", attempt_count=1)
    repository, _ = create_repository(batch)

    started = await repository.start(
        batch_id="bat_test",
        task_id="tsk_test",
    )

    assert started is batch
    assert batch.status == "running"
    assert batch.attempt_count == 2


@pytest.mark.asyncio
async def test_start_ignores_stale_task() -> None:
    """测试重试后到达的旧消息不会执行批次."""
    batch = create_batch(task_id="tsk_new")
    repository, _ = create_repository(batch)

    started = await repository.start(
        batch_id="bat_test",
        task_id="tsk_old",
    )

    assert started is None
    assert batch.status == "queued"


@pytest.mark.asyncio
async def test_request_cancel_running_batch() -> None:
    """测试运行中批次进入协作式取消状态."""
    batch = create_batch(status="running")
    repository, _ = create_repository(batch)

    result = await repository.request_cancel("bat_test")

    assert result.status == "cancelling"
    assert result.cancel_requested_at is not None


@pytest.mark.asyncio
async def test_retry_assigns_new_task_id() -> None:
    """测试业务重试生成新的 Celery 任务标识."""
    batch = create_batch(status="failed", error="failed")
    repository, _ = create_repository(batch)

    result = await repository.retry(
        "bat_test",
        task_id="tsk_retry",
    )

    assert result.status == "queued"
    assert result.task_id == "tsk_retry"
    assert result.error is None


@pytest.mark.asyncio
async def test_mark_retrying_preserves_task_id() -> None:
    """测试自动重试复用任务标识并保留执行进度."""
    batch = create_batch(
        status="running",
        attempt_count=1,
        completed_count=2,
        succeeded_count=2,
        error="temporary failure",
    )
    repository, _ = create_repository(batch)

    result = await repository.mark_retrying(
        "bat_test",
        error="database unavailable",
    )

    assert result.status == "retrying"
    assert result.task_id == "tsk_test"
    assert result.attempt_count == 1
    assert result.completed_count == 2
    assert result.succeeded_count == 2
    assert result.error == "database unavailable"


@pytest.mark.asyncio
async def test_mark_partially_succeeded() -> None:
    """测试批次可以记录成功和失败条目数量."""
    batch = create_batch(status="running", total_count=3)
    repository, _ = create_repository(batch)
    response = {"succeeded_count": 2, "failed_count": 1}

    result = await repository.mark_partially_succeeded(
        batch_id="bat_test",
        result=response,
        succeeded_count=2,
        failed_count=1,
    )

    assert result.status == "partially_succeeded"
    assert result.completed_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.result == response


@pytest.mark.asyncio
async def test_retry_partially_succeeded_batch() -> None:
    """测试部分成功批次可以重新提交失败条目."""
    batch = create_batch(
        status="partially_succeeded",
        completed_count=2,
        succeeded_count=1,
        failed_count=1,
    )
    repository, _ = create_repository(batch)

    result = await repository.retry(
        "bat_test",
        task_id="tsk_retry",
    )

    assert result.status == "queued"
    assert result.completed_count == 1
    assert result.succeeded_count == 1
    assert result.failed_count == 0
