"""批次执行尝试仓储

提供批次执行尝试的创建、查询和状态迁移能力。

核心功能：
  - create_attempt: 创建执行尝试
  - create_next_attempt: 创建下一次执行尝试
  - get_latest_attempt: 获取最近一次执行尝试
  - mark_started: 标记执行尝试开始
  - mark_finished: 标记当前执行尝试结束
  - mark_retry_scheduled: 记录失败及下一次重试时间
"""

from datetime import timedelta

from sqlalchemy import func, select

from datamind.db.models.attempts import Attempt
from datamind.db.repositories.base import BaseRepository
from datamind.utils.generator import generate_random_id


class AttemptRepository(BaseRepository):
    """批次执行尝试仓储"""

    def create_attempt(
            self,
            *,
            batch_id: str,
            task_id: str,
            attempt_number: int,
    ) -> Attempt:
        """创建等待执行的批次尝试"""
        if attempt_number < 1:
            raise ValueError("attempt_number 必须大于 0")

        new_attempt = Attempt(
            attempt_id=generate_random_id(prefix="att"),
            batch_id=batch_id,
            task_id=task_id,
            attempt_number=attempt_number,
            status="queued",
        )
        self.add(new_attempt)
        return new_attempt

    async def create_next_attempt(
            self,
            *,
            batch_id: str,
            task_id: str,
    ) -> Attempt:
        """按照已有历史创建下一次等待执行的批次尝试"""
        stmt = select(
            func.coalesce(func.max(Attempt.attempt_number), 0)
        ).where(
            Attempt.batch_id == batch_id
        )
        result = await self.session.execute(stmt)
        attempt_number = int(result.scalar_one()) + 1
        return self.create_attempt(
            batch_id=batch_id,
            task_id=task_id,
            attempt_number=attempt_number,
        )

    async def get_latest_attempt(
            self,
            batch_id: str,
    ) -> Attempt | None:
        """返回批次最近一次执行尝试。"""
        stmt = (
            select(Attempt)
            .where(Attempt.batch_id == batch_id)
            .order_by(Attempt.attempt_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_started(
            self,
            *,
            batch_id: str,
            task_id: str,
            attempt_number: int,
            worker_id: str | None,
    ) -> Attempt:
        """创建或启动当前任务对应的批次执行尝试"""
        stmt = (
            select(Attempt)
            .where(
                Attempt.batch_id == batch_id,
                Attempt.task_id == task_id,
                Attempt.status == "queued",
            )
            .order_by(Attempt.attempt_number.desc())
            .limit(1)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        attempt = result.scalar_one_or_none()

        if attempt is None:
            attempt = self.create_attempt(
                batch_id=batch_id,
                task_id=task_id,
                attempt_number=attempt_number,
            )

        attempt.task_id = task_id
        attempt.status = "running"
        attempt.worker_id = worker_id
        attempt.error = None
        attempt.retry_scheduled_at = None
        attempt.started_at = func.statement_timestamp()
        attempt.finished_at = None
        return attempt

    async def mark_finished(
            self,
            *,
            batch_id: str,
            status: str,
            error: str | None = None,
    ) -> Attempt | None:
        """结束批次当前正在运行的执行尝试"""
        if status not in {
            "succeeded",
            "partially_succeeded",
            "failed",
            "cancelled",
        }:
            raise ValueError(f"不支持的执行尝试状态: {status}")

        attempt = await self._latest(
            batch_id=batch_id,
            statuses={"queued", "running"},
        )
        if attempt is None:
            return None

        attempt.status = status
        attempt.error = error
        attempt.finished_at = func.statement_timestamp()
        return attempt

    async def mark_retry_scheduled(
            self,
            *,
            batch_id: str,
            error: str,
            retry_in_seconds: int,
    ) -> Attempt | None:
        """记录本次失败和下一次自动重试时间"""
        attempt = await self._latest(
            batch_id=batch_id,
            statuses={"running"},
        )
        if attempt is None:
            return None

        now = func.statement_timestamp()
        attempt.status = "failed"
        attempt.error = error
        attempt.finished_at = now
        attempt.retry_scheduled_at = now + timedelta(
            seconds=max(retry_in_seconds, 0)
        )
        return attempt

    async def _latest(
            self,
            *,
            batch_id: str,
            statuses: set[str],
    ) -> Attempt | None:
        """锁定并返回批次最新的指定状态尝试"""
        stmt = (
            select(Attempt)
            .where(
                Attempt.batch_id == batch_id,
                Attempt.status.in_(statuses),
            )
            .order_by(Attempt.attempt_number.desc())
            .limit(1)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
