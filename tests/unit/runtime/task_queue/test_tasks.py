"""Celery 批量协调与分片任务测试

验证批次协调任务的分片发布、失败处理和分片独立重试行为。

核心功能：
  - test_execute_batch_dispatches_non_overlapping_chunks:
    验证协调任务发布互不重叠的分片
  - test_execute_batch_marks_failed_when_dispatch_fails:
    验证分片发布失败时结束批次
  - test_execute_batch_chunk_retries_independently:
    验证分片发生瞬时异常时独立重试
  - test_execute_batch_chunk_marks_range_after_retry_limit:
    验证分片重试耗尽后标记对应范围
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from celery.exceptions import Retry

import datamind.runtime.task_queue.tasks as task_module


def install_dependencies(
        monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock]:
    """安装不连接运行时和 Broker 的任务依赖"""
    worker = MagicMock()
    publisher = MagicMock()
    monkeypatch.setitem(vars(task_module), "get_runtime_task_worker", lambda: worker)
    monkeypatch.setitem(vars(task_module), "TaskPublisher", lambda: publisher)
    monkeypatch.setitem(
        vars(task_module),
        "generate_random_id",
        MagicMock(side_effect=[
            "shd_1", "tsk_1",
            "shd_2", "tsk_2",
            "shd_3", "tsk_3",
        ]),
    )
    monkeypatch.setitem(
        vars(task_module),
        "get_task_queue_config",
        lambda: SimpleNamespace(
            max_retries=3,
            retry_backoff_seconds=5,
            batch_chunk_size=20,
        ),
    )
    return worker, publisher


def test_execute_batch_dispatches_non_overlapping_chunks(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调任务将 45 条请求拆为三个无重叠分片"""
    worker, publisher = install_dependencies(monkeypatch)
    worker.prepare_batch.return_value = 45
    task_module.execute_batch.push_request(id="tsk_parent", hostname="worker-a")
    try:
        task_module.execute_batch.run(batch_id="bat_test")
    finally:
        task_module.execute_batch.pop_request()

    worker.prepare_batch.assert_called_once_with(
        batch_id="bat_test",
        task_id="tsk_parent",
        worker_id="worker-a",
    )
    assert publisher.submit_batch_chunk.call_args_list == [
        call(batch_id="bat_test", shard_id="shd_1", task_id="tsk_1", start_index=0, end_index=20),
        call(batch_id="bat_test", shard_id="shd_2", task_id="tsk_2", start_index=20, end_index=40),
        call(batch_id="bat_test", shard_id="shd_3", task_id="tsk_3", start_index=40, end_index=45),
    ]
    worker.register_batch_shards.assert_called_once_with(
        batch_id="bat_test",
        shards=[
            {"shard_id": "shd_1", "task_id": "tsk_1", "start_index": 0, "end_index": 20},
            {"shard_id": "shd_2", "task_id": "tsk_2", "start_index": 20, "end_index": 40},
            {"shard_id": "shd_3", "task_id": "tsk_3", "start_index": 40, "end_index": 45},
        ],
    )


def test_execute_batch_marks_failed_when_dispatch_fails(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调或发布失败直接结束批次且不重复分片"""
    worker, publisher = install_dependencies(monkeypatch)
    worker.prepare_batch.return_value = 20
    publisher.submit_batch_chunk.side_effect = RuntimeError("broker down")
    task_module.execute_batch.push_request(id="tsk_parent")
    try:
        with pytest.raises(RuntimeError, match="broker down"):
            task_module.execute_batch.run(batch_id="bat_test")
    finally:
        task_module.execute_batch.pop_request()

    worker.mark_batch_failed.assert_called_once_with(
        batch_id="bat_test",
        error="broker down",
    )


def test_execute_batch_chunk_retries_independently(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试分片的瞬时异常不会重跑其他分片"""
    worker, _publisher = install_dependencies(monkeypatch)
    worker.execute_batch_chunk.side_effect = RuntimeError("temporary")
    retry = MagicMock(side_effect=Retry())
    monkeypatch.setitem(vars(task_module.execute_batch_chunk), "retry", retry)
    task_module.execute_batch_chunk.push_request(
        id="tsk_chunk",
        hostname="worker-b",
        retries=1,
    )
    try:
        with pytest.raises(Retry):
            task_module.execute_batch_chunk.run(
                batch_id="bat_test",
                shard_id="shd_test",
                start_index=20,
                end_index=40,
            )
    finally:
        task_module.execute_batch_chunk.pop_request()

    retry.assert_called_once()
    assert retry.call_args.kwargs["countdown"] == 10
    worker.mark_batch_chunk_retrying.assert_called_once_with(
        shard_id="shd_test",
        error="temporary",
    )
    worker.mark_batch_chunk_failed.assert_not_called()


def test_execute_batch_chunk_marks_range_after_retry_limit(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试分片重试耗尽后只标记自己的全局下标范围"""
    worker, _publisher = install_dependencies(monkeypatch)
    worker.execute_batch_chunk.side_effect = RuntimeError("permanent")
    task_module.execute_batch_chunk.push_request(id="tsk_chunk", retries=3)
    try:
        with pytest.raises(RuntimeError, match="permanent"):
            task_module.execute_batch_chunk.run(
                batch_id="bat_test",
                shard_id="shd_test",
                start_index=40,
                end_index=45,
            )
    finally:
        task_module.execute_batch_chunk.pop_request()

    worker.mark_batch_chunk_failed.assert_called_once_with(
        batch_id="bat_test",
        shard_id="shd_test",
        start_index=40,
        end_index=45,
        error="permanent",
    )
