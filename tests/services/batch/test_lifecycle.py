"""批次生命周期服务测试

验证批次取消和重新提交时的状态持久化与任务队列交互。

核心功能：
  - test_cancel_updates_state_and_revokes_task:
    验证取消批次后发送任务撤销消息
  - test_retry_updates_state_and_submits_new_task:
    验证重试批次后发布新的执行任务
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.batch as batch_module
from datamind.services.batch import BatchLifecycleService


class FakeUnitOfWork:
    """提供批次服务测试所需的异步工作单元"""

    session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        """进入测试工作单元"""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """退出测试工作单元"""


def create_batch(**overrides: object) -> SimpleNamespace:
    """创建批次状态测试对象"""
    values = {
        "batch_id": "bat_test",
        "task_id": "tsk_test",
        "status": "queued",
        "total_count": 2,
        "completed_count": 0,
        "succeeded_count": 0,
        "failed_count": 0,
        "attempt_count": 0,
        "created_at": None,
        "started_at": None,
        "finished_at": None,
        "cancel_requested_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def replace_batch_dependency(
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        replacement: object,
) -> None:
    """替换批次服务依赖并在测试结束后自动恢复"""
    monkeypatch.setattr(batch_module, name, replacement)


@pytest.mark.asyncio
async def test_cancel_updates_state_and_revokes_task(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试取消批次后发送任务撤销消息"""
    batch = create_batch(status="cancelled")
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.request_cancel = AsyncMock(return_value=batch)
    attempt_repository = MagicMock()
    attempt_repository.mark_finished = AsyncMock()
    publisher = MagicMock()
    replace_batch_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_batch_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _session: repository,
    )
    replace_batch_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _session: attempt_repository,
    )

    result = await BatchLifecycleService(
        task_publisher=publisher
    ).cancel(batch_id="bat_test")

    assert result["status"] == "cancelled"
    repository.request_cancel.assert_awaited_once_with("bat_test")
    attempt_repository.mark_finished.assert_awaited_once_with(
        batch_id="bat_test",
        status="cancelled",
    )
    publisher.revoke.assert_called_once_with("tsk_test")


@pytest.mark.asyncio
async def test_retry_updates_state_and_submits_new_task(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重试批次后发布新的执行任务"""
    batch = create_batch(task_id="tsk_new")
    repository = MagicMock()
    repository.retry = AsyncMock(return_value=batch)
    attempt_repository = MagicMock()
    attempt_repository.create_next_attempt = AsyncMock()
    publisher = MagicMock()
    replace_batch_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_batch_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _session: repository,
    )
    replace_batch_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _session: attempt_repository,
    )
    replace_batch_dependency(
        monkeypatch,
        "generate_random_id",
        lambda **_kwargs: "tsk_new",
    )

    result = await BatchLifecycleService(
        task_publisher=publisher
    ).retry(batch_id="bat_test")

    assert result["task_id"] == "tsk_new"
    repository.retry.assert_awaited_once_with(
        "bat_test",
        task_id="tsk_new",
    )
    attempt_repository.create_next_attempt.assert_awaited_once_with(
        batch_id="bat_test",
        task_id="tsk_new",
    )
    publisher.submit_batch.assert_called_once_with(
        batch_id="bat_test",
        task_id="tsk_new",
    )
