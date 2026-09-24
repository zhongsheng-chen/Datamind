"""批次生命周期服务.

负责批量预测任务的取消和重试，并协调数据库状态与任务队列。

核心功能：
  - cancel: 请求取消批量预测任务
  - retry: 重新提交可重试的批量预测任务

使用示例：
  from datamind.services.batch import BatchLifecycleService

  result = await BatchLifecycleService().retry(
      batch_id="bat_0123456789abcdef",
  )
"""

from typing import Any

import structlog

from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AttemptRepository,
    BatchRepository,
)
from datamind.runtime.task_queue import (
    TaskDispatchError,
    TaskPublisher,
)
from datamind.utils.datetime import format_iso_utc
from datamind.utils.generator import generate_random_id


logger = structlog.get_logger(__name__)


class BatchLifecycleService:
    """批次生命周期服务.

    通过工作单元持久化批次状态，并在事务完成后向任务队列
    发布重试或撤销消息。
    """

    def __init__(
            self,
            *,
            task_publisher: TaskPublisher | None = None,
    ) -> None:
        """初始化批次生命周期服务.

        参数：
            task_publisher: 任务发布器，默认使用 TaskPublisher
        """
        self.task_publisher = task_publisher or TaskPublisher()

    async def cancel(
            self,
            *,
            batch_id: str,
    ) -> dict[str, Any]:
        """请求取消批量预测任务.

        参数：
            batch_id: 批次 ID

        返回：
            更新后的批次状态

        异常：
            ValueError: 批次不存在或当前状态不允许取消
        """
        async with UnitOfWork() as uow:
            repository = BatchRepository(uow.session)
            batch = await repository.get_batch(batch_id)

            if batch is None:
                raise ValueError(f"批次不存在: {batch_id}")

            task_id = batch.task_id
            batch = await repository.request_cancel(batch_id)
            if batch.status == "cancelled":
                await AttemptRepository(uow.session).mark_finished(
                    batch_id=batch_id,
                    status="cancelled",
                )
            result = self._to_dict(batch)

        try:
            self.task_publisher.revoke(task_id)
        except TaskDispatchError as exc:
            logger.warning(
                "批量预测任务撤销消息发送失败",
                batch_id=batch_id,
                task_id=task_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

        return result

    async def retry(
            self,
            *,
            batch_id: str,
    ) -> dict[str, Any]:
        """重新提交可重试的批量预测任务.

        参数：
            batch_id: 批次 ID

        返回：
            重新排队后的批次状态

        异常：
            ValueError: 批次不存在或当前状态不允许重试
            TaskDispatchError: 批量预测任务无法发布
        """
        task_id = generate_random_id(prefix="tsk")

        async with UnitOfWork() as uow:
            repository = BatchRepository(uow.session)
            batch = await repository.retry(
                batch_id,
                task_id=task_id,
            )
            await AttemptRepository(
                uow.session
            ).create_next_attempt(
                batch_id=batch_id,
                task_id=task_id,
            )
            result = self._to_dict(batch)

        try:
            self.task_publisher.submit_batch(
                batch_id=batch_id,
                task_id=task_id,
            )
        except TaskDispatchError as exc:
            error = str(exc) or exc.__class__.__name__

            async with UnitOfWork() as uow:
                await BatchRepository(uow.session).mark_failed(
                    batch_id=batch_id,
                    error=error,
                )
                await AttemptRepository(uow.session).mark_finished(
                    batch_id=batch_id,
                    status="failed",
                    error=error,
                )

            raise

        return result

    @staticmethod
    def _to_dict(batch: Any) -> dict[str, Any]:
        """转换批次状态为响应字典."""
        completed_count = int(
            getattr(batch, "completed_count", 0) or 0
        )
        succeeded_count = int(
            getattr(batch, "succeeded_count", 0) or 0
        )
        failed_count = int(
            getattr(batch, "failed_count", 0) or 0
        )
        attempt_count = int(
            getattr(batch, "attempt_count", 0) or 0
        )
        return {
            "batch_id": batch.batch_id,
            "task_id": batch.task_id,
            "status": batch.status,
            "total_count": batch.total_count,
            "completed_count": completed_count,
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "attempt_count": attempt_count,
            "retry_count": max(attempt_count - 1, 0),
            "created_at": format_iso_utc(batch.created_at),
            "started_at": format_iso_utc(batch.started_at),
            "finished_at": format_iso_utc(batch.finished_at),
            "cancel_requested_at": format_iso_utc(
                batch.cancel_requested_at
            ),
        }
