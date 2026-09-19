"""批次执行分片仓储测试

验证批次执行分片的创建、启动和结束状态迁移。

核心功能：
  - test_create_shard:
    验证创建等待执行的批次分片
  - test_mark_started_records_worker:
    验证分片进入运行状态并记录 Worker
  - test_mark_finished_records_terminal_state:
    验证分片进入最终状态并记录完成时间
  - test_mark_open_shards_failed:
    验证批次中未结束的分片统一进入失败状态
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.models.shards import Shard
from datamind.db.repositories.shard import ShardRepository


def create_repository(scalar: object = None) -> tuple[ShardRepository, MagicMock]:
    """创建使用会话替身的分片仓储"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    return (
        ShardRepository(cast(AsyncSession, cast(object, session))),
        session,
    )


def create_shard(**overrides: object) -> Shard:
    """创建分片测试对象"""
    values: dict[str, object] = {
        "shard_id": "shd_test",
        "attempt_id": "att_test",
        "batch_id": "bat_test",
        "task_id": "tsk_test",
        "start_index": 0,
        "end_index": 20,
        "status": "queued",
    }
    values.update(overrides)
    return Shard(**values)


def test_create_shard() -> None:
    """测试创建等待执行的批次分片"""
    repository, session = create_repository()
    new_shard = repository.create_shard(
        shard_id="shd_test",
        attempt_id="att_test",
        batch_id="bat_test",
        task_id="tsk_test",
        start_index=0,
        end_index=20,
    )
    assert new_shard.attempt_id == "att_test"
    assert new_shard.status == "queued"
    session.add.assert_called_once_with(new_shard)


@pytest.mark.asyncio
async def test_mark_started_records_worker() -> None:
    """测试分片进入运行状态并记录 Worker"""
    shard = create_shard()
    repository, _ = create_repository(shard)
    result = await repository.mark_started(
        shard_id="shd_test",
        worker_id="worker-a",
    )
    assert result is shard
    assert shard.status == "running"
    assert shard.worker_id == "worker-a"
    assert str(shard.started_at) == "statement_timestamp()"


@pytest.mark.asyncio
async def test_mark_finished_records_terminal_state() -> None:
    """测试分片进入最终状态并记录完成时间"""
    shard = create_shard(status="running")
    repository, _ = create_repository(shard)
    result = await repository.mark_finished(
        shard_id="shd_test",
        status="succeeded",
    )
    assert result is shard
    assert shard.status == "succeeded"
    assert str(shard.finished_at) == "statement_timestamp()"


@pytest.mark.asyncio
async def test_mark_open_shards_failed() -> None:
    """测试批次中未结束的分片统一进入失败状态"""
    shards = [
        create_shard(shard_id="shd_queued"),
        create_shard(shard_id="shd_running", status="running"),
    ]
    repository, session = create_repository()
    session.execute.return_value.scalars.return_value.all.return_value = shards

    await repository.mark_open_shards_failed(
        batch_id="bat_test",
        error="batch failed",
    )

    for shard in shards:
        assert shard.status == "failed"
        assert shard.error == "batch failed"
        assert str(shard.finished_at) == "statement_timestamp()"
