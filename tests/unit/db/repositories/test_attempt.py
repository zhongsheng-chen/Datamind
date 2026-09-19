"""批次执行尝试仓储测试

验证批次执行尝试的创建、启动、结束和自动重试状态迁移。

核心功能：
  - test_create_attempt:
    验证创建等待执行的尝试
  - test_create_next_attempt:
    验证按照已有历史生成下一次尝试
  - test_mark_started:
    验证尝试进入运行状态并记录 Worker
  - test_mark_finished:
    验证尝试进入最终状态
  - test_mark_retry_scheduled:
    验证失败尝试记录自动重试时间
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.models.attempts import Attempt
from datamind.db.repositories.attempt import AttemptRepository


def create_repository(
        *,
        scalar: object = None,
) -> tuple[AttemptRepository, MagicMock]:
    """创建使用会话替身的执行尝试仓储"""
    result = MagicMock()
    result.scalar_one.return_value = scalar
    result.scalar_one_or_none.return_value = scalar
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    repository = AttemptRepository(
        cast(AsyncSession, cast(object, session))
    )
    return repository, session


def create_attempt(**overrides: object) -> Attempt:
    """创建执行尝试测试对象"""
    values: dict[str, object] = {
        "attempt_id": "att_test",
        "batch_id": "bat_test",
        "task_id": "tsk_test",
        "attempt_number": 1,
        "status": "queued",
    }
    values.update(overrides)
    return Attempt(**values)


def test_create_attempt() -> None:
    """测试创建等待执行的尝试"""
    repository, session = create_repository()

    attempt = repository.create_attempt(
        batch_id="bat_test",
        task_id="tsk_test",
        attempt_number=1,
    )

    assert attempt.attempt_id.startswith("att_")
    assert attempt.status == "queued"
    assert attempt.attempt_number == 1
    session.add.assert_called_once_with(attempt)


@pytest.mark.asyncio
async def test_create_next_attempt() -> None:
    """测试按照已有历史生成下一次尝试"""
    repository, _ = create_repository(scalar=2)

    attempt = await repository.create_next_attempt(
        batch_id="bat_test",
        task_id="tsk_retry",
    )

    assert attempt.attempt_number == 3
    assert attempt.task_id == "tsk_retry"


@pytest.mark.asyncio
async def test_mark_started() -> None:
    """测试尝试进入运行状态并记录 Worker"""
    attempt = create_attempt(attempt_number=2)
    repository, _ = create_repository(scalar=attempt)

    result = await repository.mark_started(
        batch_id="bat_test",
        task_id="tsk_test",
        attempt_number=1,
        worker_id="worker-1",
    )

    assert result is attempt
    assert attempt.attempt_number == 2
    assert attempt.status == "running"
    assert attempt.worker_id == "worker-1"
    assert attempt.started_at is not None
    assert str(attempt.started_at) == "statement_timestamp()"


@pytest.mark.asyncio
async def test_mark_finished() -> None:
    """测试尝试进入最终状态"""
    attempt = create_attempt(status="running")
    repository, _ = create_repository(scalar=attempt)

    result = await repository.mark_finished(
        batch_id="bat_test",
        status="succeeded",
    )

    assert result is attempt
    assert attempt.status == "succeeded"
    assert attempt.finished_at is not None
    assert str(attempt.finished_at) == "statement_timestamp()"


@pytest.mark.asyncio
async def test_mark_retry_scheduled() -> None:
    """测试失败尝试记录自动重试时间"""
    attempt = create_attempt(status="running")
    repository, _ = create_repository(scalar=attempt)

    result = await repository.mark_retry_scheduled(
        batch_id="bat_test",
        error="temporary error",
        retry_in_seconds=10,
    )

    assert result is attempt
    assert attempt.status == "failed"
    assert attempt.error == "temporary error"
    assert attempt.finished_at is not None
    assert attempt.retry_scheduled_at is not None
    assert "statement_timestamp()" in str(attempt.retry_scheduled_at)
    assert str(attempt.finished_at) == "statement_timestamp()"
