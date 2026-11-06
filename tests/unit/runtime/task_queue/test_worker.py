"""批量协调、分片执行和终态汇总测试.

验证运行时任务执行器准备批次、执行分片及汇总批次终态的行为。

核心功能：
  - test_prepare_batch_creates_records_before_dispatch:
    验证发布分片前启动尝试并准备请求记录
  - test_execute_batch_chunk_uses_global_indices:
    验证分片执行使用全局批次下标
  - test_finalize_batch_updates_progress_before_terminal_state:
    验证未完成全部分片时仅更新批次进度
  - test_last_chunk_finalizes_partial_success_once:
    验证最后一个分片写入部分成功终态
  - test_batch_terminal_log_counts_duration_and_no_duplicate:
    验证批次汇总日志包含计数和耗时，重复完成通知不重复记录结果
  - test_batch_task_exception_logs_error_with_business_counts:
    验证任务级异常与逐条业务失败分别记录，并保留批次和持久化计数
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.runtime.task_queue.worker as worker_module


class FakeUnitOfWork:
    """提供不访问数据库的异步工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc_value: BaseException | None,
            _traceback: Any,
    ) -> None:
        return None


def create_batch(
        **overrides: Any,
) -> SimpleNamespace:
    """创建可由请求 Schema 还原的批次记录."""
    values = {
        "batch_id": "bat_test",
        "task_id": "tsk_test",
        "attempt_count": 1,
        "started_at": None,
        "created_at": None,
        "status": "running",
        "total_count": 2,
        "completed_count": 0,
        "succeeded_count": 0,
        "failed_count": 0,
        "payload": {
            "model_name": "scorecard",
            "deployment_id": None,
            "instances": [
                {"features": {"age": 35}},
                {"features": {"age": 45}},
            ],
        },
        "user": "admin",
        "ip": "127.0.0.1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def create_worker(
        service: MagicMock,
) -> worker_module.RuntimeTaskWorker:
    """跳过线程启动并注入受控运行时服务."""
    worker = object.__new__(worker_module.RuntimeTaskWorker)
    worker._service = service
    return worker


def replace_worker_dependency(
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        replacement: object,
) -> None:
    """替换执行器模块依赖并在测试结束后自动恢复."""
    monkeypatch.setitem(vars(worker_module), name, replacement)


@pytest.mark.asyncio
async def test_prepare_batch_creates_records_before_dispatch(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调阶段先启动尝试再一次性准备全部请求记录."""
    repository = MagicMock()
    repository.start = AsyncMock(return_value=create_batch())
    attempt_repository = MagicMock()
    attempt_repository.mark_started = AsyncMock()
    service = MagicMock()
    service.prepare_batch_task = AsyncMock(return_value=2)
    replace_worker_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )
    replace_worker_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _s: attempt_repository,
    )

    task_logger = MagicMock()
    monkeypatch.setattr(worker_module, "logger", task_logger)
    count = await create_worker(service)._prepare_batch(
        batch_id="bat_test",
        task_id="tsk_test",
        worker_id="worker-a",
    )

    assert count == 2
    task_logger.info.assert_called_once()
    assert task_logger.info.call_args.args == ("批量预测任务开始执行",)
    assert task_logger.info.call_args.kwargs["status"] == "running"
    assert "batch_status" not in task_logger.info.call_args.kwargs
    attempt_repository.mark_started.assert_awaited_once_with(
        batch_id="bat_test",
        task_id="tsk_test",
        attempt_number=1,
        worker_id="worker-a",
    )
    service.prepare_batch_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_batch_chunk_uses_global_indices(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试分片执行传递半开区间的全局 batch_index."""
    batch = create_batch()
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.is_cancel_requested = AsyncMock(return_value=False)
    service = MagicMock()
    service.execute_batch_task = AsyncMock(return_value={"success": True})
    worker = create_worker(service)
    worker._finalize_batch_if_complete = AsyncMock()
    worker._finish_batch_chunk = AsyncMock()
    shard_repository = MagicMock()
    shard_repository.mark_started = AsyncMock(return_value=SimpleNamespace(
        status="running",
    ))
    replace_worker_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )
    replace_worker_dependency(
        monkeypatch,
        "ShardRepository",
        lambda _s: shard_repository,
    )

    await worker._execute_batch_chunk(
        batch_id="bat_test",
        shard_id="shd_test",
        start_index=1,
        end_index=2,
        worker_id="worker-b",
    )

    awaited_call = service.execute_batch_task.await_args
    assert awaited_call is not None
    call_kwargs = awaited_call.kwargs
    assert call_kwargs["batch_indices"] == [1]
    assert call_kwargs["prepare_records"] is False
    assert call_kwargs["raise_errors"] is True
    shard_repository.mark_started.assert_awaited_once_with(
        shard_id="shd_test",
        worker_id="worker-b",
    )
    worker._finish_batch_chunk.assert_awaited_once_with(
        batch_id="bat_test",
        shard_id="shd_test",
        start_index=1,
        end_index=2,
    )
    worker._finalize_batch_if_complete.assert_awaited_once_with("bat_test")


@pytest.mark.asyncio
async def test_finalize_batch_updates_progress_before_terminal_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未完成全部分片时只更新进度且不提前结束批次."""
    batch = create_batch(total_count=4)
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    service = MagicMock()
    worker = create_worker(service)
    worker._build_batch_result = AsyncMock(return_value=({}, 2, 1))
    replace_worker_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )

    await worker._finalize_batch_if_complete("bat_test")

    assert batch.completed_count == 3
    assert batch.succeeded_count == 2
    assert batch.failed_count == 1
    repository.mark_succeeded.assert_not_called()
    repository.mark_partially_succeeded.assert_not_called()


@pytest.mark.asyncio
async def test_last_chunk_finalizes_partial_success_once(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试最后一个分片在批次锁内写入部分成功终态."""
    batch = create_batch(total_count=2)
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.mark_partially_succeeded = AsyncMock()
    attempt_repository = MagicMock()
    attempt_repository.mark_finished = AsyncMock()
    result = {"batch_id": "bat_test", "succeeded_count": 1, "failed_count": 1}
    worker = create_worker(MagicMock())
    worker._build_batch_result = AsyncMock(return_value=(result, 1, 1))
    replace_worker_dependency(monkeypatch, "UnitOfWork", FakeUnitOfWork)
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )
    replace_worker_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _s: attempt_repository,
    )

    await worker._finalize_batch_if_complete("bat_test")

    repository.mark_partially_succeeded.assert_awaited_once_with(
        batch_id="bat_test",
        result=result,
        succeeded_count=1,
        failed_count=1,
    )
    attempt_repository.mark_finished.assert_awaited_once_with(
        batch_id="bat_test",
        status="partially_succeeded",
        error=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "succeeded,failed,status",
    [
        (2, 0, "succeeded"),
        (1, 1, "partially_succeeded"),
        (0, 2, "failed"),
    ],
)
async def test_batch_terminal_log_counts_duration_and_no_duplicate(
        monkeypatch,
        succeeded,
        failed,
        status,
):
    """测试批次汇总日志包含计数和耗时，重复完成通知不重复记录结果."""
    from datetime import (
        datetime,
        timedelta,
        timezone,
    )
    from structlog.testing import capture_logs

    batch = create_batch(started_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)

    for name in ["mark_succeeded", "mark_partially_succeeded", "mark_failed"]:
        setattr(repository, name, AsyncMock())

    attempts = MagicMock(mark_finished=AsyncMock())
    worker = create_worker(MagicMock())
    worker._build_batch_result = AsyncMock(return_value=({}, succeeded, failed))
    replace_worker_dependency(
        monkeypatch,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )
    replace_worker_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _s: attempts,
    )

    with capture_logs() as logs:
        await worker._finalize_batch_if_complete("bat_test")
        batch.status = status
        await worker._finalize_batch_if_complete("bat_test")

    terminal = [log for log in logs if log["event"] == "批量预测任务执行完成"]

    assert len(terminal) == 1
    assert terminal[0]["log_level"] == "info"
    assert terminal[0]["batch_id"] == "bat_test"
    assert terminal[0]["total_count"] == 2
    assert terminal[0]["succeeded_count"] == succeeded
    assert terminal[0]["failed_count"] == failed
    assert terminal[0]["status"] == status
    assert "batch_status" not in terminal[0]
    assert terminal[0]["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_batch_task_exception_logs_error_with_business_counts(
        monkeypatch,
):
    """测试任务级异常与逐条业务失败分别记录，并保留批次和持久化计数."""
    from datetime import (
        datetime,
        timezone,
    )
    from structlog.testing import capture_logs

    batch = create_batch(
        status="partially_succeeded",
        succeeded_count=1,
        failed_count=1,
        started_at=datetime.now(timezone.utc),
    )
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.mark_partially_succeeded = AsyncMock()
    attempts = MagicMock(mark_finished=AsyncMock())
    shards = MagicMock(mark_open_shards_failed=AsyncMock())
    replace_worker_dependency(
        monkeypatch,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    replace_worker_dependency(
        monkeypatch,
        "BatchRepository",
        lambda _s: repository,
    )
    replace_worker_dependency(
        monkeypatch,
        "AttemptRepository",
        lambda _s: attempts,
    )
    replace_worker_dependency(
        monkeypatch,
        "ShardRepository",
        lambda _s: shards,
    )
    monkeypatch.setattr(
        worker_module.RuntimeTaskWorker,
        "_build_batch_result",
        AsyncMock(return_value=({}, 1, 1)),
    )

    with capture_logs() as logs:
        await worker_module.RuntimeTaskWorker._mark_batch_failed(
            batch_id="bat_test",
            error="broker unavailable",
        )

    result = next(log for log in logs if log["event"] == "批量预测任务执行失败")

    assert result["log_level"] == "error"
    assert result["batch_id"] == "bat_test"
    assert result["error"] == "broker unavailable"
    assert result["total_count"] == 2
    assert result["succeeded_count"] == 1
    assert result["failed_count"] == 1
    assert result["duration_ms"] >= 0
