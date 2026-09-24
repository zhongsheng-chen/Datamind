"""预测批次仓储.

提供预测批次记录的创建、查询和状态迁移能力。

核心功能：
  - get_batch: 获取预测批次
  - create_batch: 创建预测批次
  - start: 标记预测批次开始执行
  - request_cancel: 请求取消预测批次
  - retry: 重新提交失败或已取消的预测批次
  - mark_retrying: 标记预测批次等待自动重试
  - mark_succeeded: 标记预测批次执行成功
  - mark_partially_succeeded: 标记预测批次部分成功
  - mark_failed: 标记预测批次执行失败
  - mark_cancelled: 标记预测批次已取消
  - is_cancel_requested: 判断预测批次是否已请求取消

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.batch import BatchRepository

  async with UnitOfWork() as uow:
      repo = BatchRepository(
          uow.session
      )

      batch = repo.create_batch(
          batch_id="bat_0123456789abcdef",
          task_id="tsk_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          model_name="scorecard",
          deployment_id=None,
          environment="production",
          payload={
              "model_name": "scorecard",
              "instances": [
                  {
                      "features": {
                          "age": 35,
                      },
                  },
              ],
          },
          total_count=1,
          source="http",
          user="admin",
          ip="127.0.0.1",
      )
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from datamind.db.models.batches import Batch
from datamind.db.repositories.base import BaseRepository


class BatchRepository(BaseRepository):
    """预测批次仓储."""

    async def get_batch(
            self,
            batch_id: str,
            *,
            for_update: bool = False,
    ) -> Batch | None:
        """获取预测批次.

        参数：
            batch_id: 批次 ID
            for_update: 是否锁定记录以供更新

        返回：
            预测批次对象，不存在时返回 None
        """
        stmt = select(Batch).where(
            Batch.batch_id == batch_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def create_batch(
            self,
            *,
            batch_id: str,
            task_id: str,
            model_id: str | None,
            model_name: str,
            deployment_id: str | None,
            environment: str,
            payload: dict[str, Any],
            total_count: int,
            source: str | None,
            user: str | None,
            ip: str | None,
    ) -> Batch:
        """创建等待执行的预测批次.

        参数：
            batch_id: 批次 ID
            task_id: Celery 任务 ID
            model_id: 目标模型 ID（可选）
            model_name: 模型名称
            deployment_id: 指定部署 ID（可选）
            environment: 运行环境
            payload: 批次请求负载
            total_count: 批次请求数量
            source: 请求来源（可选）
            user: 用户标识（可选）
            ip: 客户端 IP 地址（可选）

        返回：
            创建后的预测批次对象

        异常：
            ValueError: 批次请求数量小于 1
        """
        if total_count < 1:
            raise ValueError("total_count 必须大于 0")

        new_batch = Batch(
            batch_id=batch_id,
            task_id=task_id,
            model_name=model_name,
            environment=environment,
            payload=payload,
            total_count=total_count,
            completed_count=0,
            succeeded_count=0,
            failed_count=0,
            attempt_count=0,
            status="queued",
        )

        if model_id is not None:
            new_batch.model_id = model_id

        if deployment_id is not None:
            new_batch.deployment_id = deployment_id

        if source is not None:
            new_batch.source = source

        if user is not None:
            new_batch.user = user

        if ip is not None:
            new_batch.ip = ip

        self.add(new_batch)
        return new_batch

    async def start(
            self,
            *,
            batch_id: str,
            task_id: str,
    ) -> Batch | None:
        """标记预测批次开始执行.

        仅当前 Celery 任务可以启动处于 queued 或 retrying 状态的批次。

        参数：
            batch_id: 批次 ID
            task_id: Celery 任务 ID

        返回：
            更新后的预测批次对象；批次不存在、任务 ID 不匹配或
            状态不允许启动时返回 None
        """
        now = datetime.now(timezone.utc)
        batch = await self.get_batch(
            batch_id,
            for_update=True,
        )

        if (
                batch is None
                or batch.task_id != task_id
                or batch.status not in {"queued", "retrying"}
        ):
            return None

        batch.status = "running"
        batch.started_at = now
        batch.finished_at = None
        batch.attempt_count += 1
        batch.error = None
        return batch

    async def request_cancel(self, batch_id: str) -> Batch:
        """请求取消预测批次.

        等待执行的批次直接进入 cancelled 状态，运行中的批次进入
        cancelling 状态并等待执行器协作式取消。

        参数：
            batch_id: 批次 ID

        返回：
            更新后的预测批次对象

        异常：
            ValueError: 批次不存在或当前状态不允许取消
        """
        batch = await self._require_batch(batch_id)
        now = datetime.now(timezone.utc)

        if batch.status in {"queued", "retrying"}:
            batch.status = "cancelled"
            batch.cancel_requested_at = now
            batch.finished_at = now
        elif batch.status == "running":
            batch.status = "cancelling"
            batch.cancel_requested_at = now
        elif batch.status not in {"cancelling", "cancelled"}:
            raise ValueError(f"状态 {batch.status} 的批次不能取消")

        return batch

    async def retry(
            self,
            batch_id: str,
            *,
            task_id: str,
    ) -> Batch:
        """重新提交失败或已取消的预测批次.

        参数：
            batch_id: 批次 ID
            task_id: 新的 Celery 任务 ID

        返回：
            重新进入 queued 状态的预测批次对象

        异常：
            ValueError: 批次不存在或当前状态不允许重试
        """
        batch = await self._require_batch(batch_id)

        if batch.status not in {
            "partially_succeeded",
            "failed",
            "cancelled",
        }:
            raise ValueError(
                f"状态 {batch.status} 的批次不能重试"
            )

        batch.task_id = task_id
        batch.status = "queued"
        batch.result = None
        batch.error = None
        batch.completed_count = batch.succeeded_count
        batch.failed_count = 0
        batch.started_at = None
        batch.finished_at = None
        batch.cancel_requested_at = None
        return batch

    async def mark_retrying(
            self,
            batch_id: str,
            *,
            error: str,
    ) -> Batch:
        """标记预测批次等待自动重试.

        用于 Celery 自动重试，不更换任务 ID，也不清空累计执行进度。

        参数：
            batch_id: 批次 ID
            error: 本次执行失败原因

        返回：
            进入 retrying 状态的预测批次对象

        异常：
            ValueError: 批次不存在或当前状态不允许自动重试
        """
        batch = await self._require_batch(batch_id)

        if batch.status not in {"queued", "running", "retrying"}:
            raise ValueError(
                f"状态 {batch.status} 的批次不能自动重试"
            )

        batch.status = "retrying"
        batch.error = error
        batch.finished_at = None
        return batch

    async def mark_succeeded(
            self,
            *,
            batch_id: str,
            result: dict[str, Any],
    ) -> Batch:
        """标记预测批次执行成功.

        参数：
            batch_id: 批次 ID
            result: 批次执行结果

        返回：
            更新后的预测批次对象

        异常：
            ValueError: 批次不存在
            RuntimeError: 批次不在运行状态
        """
        batch = await self._require_running_batch(batch_id)
        batch.status = "succeeded"
        batch.result = result
        batch.error = None
        batch.completed_count = batch.total_count
        batch.succeeded_count = batch.total_count
        batch.failed_count = 0
        self._finish(batch)
        return batch

    async def mark_failed(
            self,
            *,
            batch_id: str,
            error: str,
            result: dict[str, Any] | None = None,
    ) -> Batch:
        """标记预测批次执行失败.

        参数：
            batch_id: 批次 ID
            error: 错误信息
            result: 批次错误响应（可选）

        返回：
            更新后的预测批次对象

        异常：
            ValueError: 批次不存在或当前状态不允许标记失败
        """
        batch = await self._require_batch(batch_id)
        if batch.status not in {
            "queued",
            "running",
            "retrying",
            "cancelling",
        }:
            raise ValueError(
                f"状态 {batch.status} 的批次不能标记为失败"
            )
        batch.status = "failed"
        batch.result = result
        batch.error = error
        batch.completed_count = batch.total_count
        batch.succeeded_count = 0
        batch.failed_count = batch.total_count
        self._finish(batch)
        return batch

    async def mark_partially_succeeded(
            self,
            *,
            batch_id: str,
            result: dict[str, Any],
            succeeded_count: int,
            failed_count: int,
    ) -> Batch:
        """标记预测批次部分成功.

        参数：
            batch_id: 批次 ID
            result: 批次执行结果
            succeeded_count: 成功记录数
            failed_count: 失败记录数

        返回：
            更新后的预测批次对象

        异常：
            ValueError: 成功或失败数量无效
            RuntimeError: 批次不在运行状态
        """
        batch = await self._require_running_batch(batch_id)

        if (
                succeeded_count < 1
                or failed_count < 1
                or succeeded_count + failed_count != batch.total_count
        ):
            raise ValueError("部分成功的批次计数无效")

        batch.status = "partially_succeeded"
        batch.result = result
        batch.error = None
        batch.completed_count = batch.total_count
        batch.succeeded_count = succeeded_count
        batch.failed_count = failed_count
        self._finish(batch)
        return batch

    async def mark_cancelled(
            self,
            *,
            batch_id: str,
            result: dict[str, Any] | None = None,
            succeeded_count: int = 0,
            failed_count: int = 0,
    ) -> Batch:
        """标记预测批次已取消.

        参数：
            batch_id: 批次 ID
            result: 批次取消响应（可选）
            succeeded_count: 取消前成功记录数
            failed_count: 取消时失败记录数

        返回：
            更新后的预测批次对象

        异常：
            ValueError: 批次不存在或当前状态不允许标记取消
        """
        batch = await self._require_batch(batch_id)
        if batch.status not in {
            "queued",
            "running",
            "retrying",
            "cancelling",
        }:
            raise ValueError(
                f"状态 {batch.status} 的批次不能标记为已取消"
            )
        batch.status = "cancelled"
        batch.result = result
        batch.error = None
        batch.completed_count = succeeded_count + failed_count
        batch.succeeded_count = succeeded_count
        batch.failed_count = failed_count
        self._finish(batch)
        return batch

    async def is_cancel_requested(self, batch_id: str) -> bool:
        """判断预测批次是否已请求取消.

        参数：
            batch_id: 批次 ID

        返回：
            批次处于 cancelling 或 cancelled 状态时返回 True，
            否则返回 False
        """
        batch = await self.get_batch(batch_id)
        return bool(
            batch is not None
            and batch.status in {"cancelling", "cancelled"}
        )

    async def _require_batch(self, batch_id: str) -> Batch:
        """获取并锁定必须存在的预测批次."""
        batch = await self.get_batch(batch_id, for_update=True)

        if batch is None:
            raise ValueError(f"预测批次不存在: {batch_id}")

        return batch

    async def _require_running_batch(
            self,
            batch_id: str,
    ) -> Batch:
        """获取并锁定必须处于运行状态的预测批次."""
        batch = await self._require_batch(batch_id)

        if batch.status != "running":
            raise RuntimeError(
                f"预测批次不在运行状态: {batch_id}"
            )

        return batch

    @staticmethod
    def _finish(batch: Batch) -> None:
        """记录预测批次结束时间."""
        batch.finished_at = datetime.now(timezone.utc)
