"""批次执行分片仓储.

提供批次执行分片的创建、查询和状态迁移能力。

核心功能：
  - create_shard: 创建执行分片
  - mark_started: 标记执行分片开始
  - mark_retrying: 标记执行分片等待重试
  - mark_finished: 写入执行分片终态
  - mark_open_shards_failed: 标记批次中未结束的分片失败
"""

from sqlalchemy import func, select

from datamind.db.models.shards import Shard
from datamind.db.repositories.base import BaseRepository


class ShardRepository(BaseRepository):
    """批次执行分片仓储."""

    def create_shard(
            self,
            *,
            shard_id: str,
            attempt_id: str,
            batch_id: str,
            task_id: str,
            start_index: int,
            end_index: int,
    ) -> Shard:
        """创建等待执行的批次分片.

        参数：
            shard_id: 分片 ID
            attempt_id: 执行尝试 ID
            batch_id: 批次 ID
            task_id: Celery 任务 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）

        返回：
            创建后的执行分片对象
        """
        new_shard = Shard(
            shard_id=shard_id,
            attempt_id=attempt_id,
            batch_id=batch_id,
            task_id=task_id,
            start_index=start_index,
            end_index=end_index,
            status="queued",
        )
        self.add(new_shard)
        return new_shard

    async def mark_started(
            self,
            *,
            shard_id: str,
            worker_id: str | None,
    ) -> Shard | None:
        """标记执行分片开始.

        已进入终态的分片保持不变。

        参数：
            shard_id: 分片 ID
            worker_id: 执行分片的 Worker 节点 ID（可选）

        返回：
            更新后的执行分片对象；分片不存在时返回 None
        """
        shard = await self._get_for_update(shard_id)
        if shard is None or shard.status in {
            "succeeded",
            "partially_succeeded",
            "failed",
            "cancelled",
        }:
            return shard

        shard.status = "running"
        shard.worker_id = worker_id
        shard.error = None
        shard.started_at = func.statement_timestamp()
        shard.finished_at = None
        return shard

    async def mark_retrying(
            self,
            *,
            shard_id: str,
            error: str,
    ) -> Shard | None:
        """标记执行分片等待重试.

        参数：
            shard_id: 分片 ID
            error: 本次执行的错误信息

        返回：
            更新后的执行分片对象；分片不存在时返回 None
        """
        shard = await self._get_for_update(shard_id)
        if shard is None:
            return None

        shard.status = "retrying"
        shard.error = error
        shard.finished_at = None
        return shard

    async def mark_finished(
            self,
            *,
            shard_id: str,
            status: str,
            error: str | None = None,
    ) -> Shard | None:
        """写入执行分片终态.

        参数：
            shard_id: 分片 ID
            status: 执行分片终态
            error: 执行错误信息（可选）

        返回：
            更新后的执行分片对象；分片不存在时返回 None

        异常：
            ValueError: 指定状态不是执行分片终态
        """
        if status not in {
            "succeeded",
            "partially_succeeded",
            "failed",
            "cancelled",
        }:
            raise ValueError(f"不支持的分片状态: {status}")

        shard = await self._get_for_update(shard_id)
        if shard is None:
            return None

        shard.status = status
        shard.error = error
        shard.finished_at = func.statement_timestamp()
        return shard

    async def mark_open_shards_failed(
            self,
            *,
            batch_id: str,
            error: str,
    ) -> None:
        """标记批次中未结束的执行分片失败.

        参数：
            batch_id: 批次 ID
            error: 批次协调失败的错误信息
        """
        stmt = (
            select(Shard)
            .where(
                Shard.batch_id == batch_id,
                Shard.status.in_({
                    "queued",
                    "running",
                    "retrying",
                }),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)

        for shard in result.scalars().all():
            shard.status = "failed"
            shard.error = error
            shard.finished_at = func.statement_timestamp()

    async def _get_for_update(self, shard_id: str) -> Shard | None:
        """锁定并获取执行分片.

        参数：
            shard_id: 分片 ID

        返回：
            锁定后的执行分片对象；分片不存在时返回 None
        """
        stmt = (
            select(Shard)
            .where(Shard.shard_id == shard_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
