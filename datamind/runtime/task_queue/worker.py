"""Celery 运行时任务执行器

在 Celery Worker 子进程中维护专用线程、异步事件循环和模型运行时实例，
为同步 Celery 任务提供批量预测与影子预测执行能力，并复用已加载模型。

核心功能：
  - RuntimeTaskWorker: 执行批量预测和影子预测任务
  - get_runtime_task_worker: 获取当前进程的运行时执行器
  - shutdown_runtime_task_worker: 关闭运行时执行器

使用示例：
  from datamind.runtime.task_queue.worker import (
      get_runtime_task_worker,
  )

  worker = get_runtime_task_worker()
  worker.prepare_batch(
      batch_id="bat_0123456789abcdef",
      task_id="tsk_0123456789abcdef",
  )
"""

import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Coroutine, cast

from datamind.context import context_scope, generate_trace_id
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AttemptRepository,
    ShardRepository,
    BatchRepository,
    RequestRepository,
)
from datamind.runtime.server.schemas import BatchPredictRequest
from datamind.runtime.task_queue.errors import BatchCancelledError


class RuntimeTaskWorker:
    """Celery 运行时任务执行器

    在当前 Worker 子进程中维护专用异步事件循环和运行时服务实例，
    为同步 Celery 任务提供批量预测与影子预测执行入口。
    """

    def __init__(self) -> None:
        """初始化运行时任务执行器

        异常：
            RuntimeError: 运行时服务初始化失败
        """
        self._loop: asyncio.AbstractEventLoop | None = None
        self._service: Any = None
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="datamind-celery-runtime",
            daemon=True,
        )
        self._startup_error: BaseException | None = None
        self._thread.start()
        self._ready.wait()

        if self._startup_error is not None:
            raise RuntimeError(
                "Celery 运行时初始化失败"
            ) from self._startup_error

    def prepare_batch(
            self,
            *,
            batch_id: str,
            task_id: str,
            worker_id: str | None = None,
    ) -> int:
        """启动批次并准备分片共享的请求记录

        参数：
            batch_id: 批次 ID
            task_id: 当前 Celery 任务 ID
            worker_id: 当前 Celery Worker 标识（可选）

        返回：
            批次包含的请求记录数量
        """
        return int(self._submit(
            self._prepare_batch(
                batch_id=batch_id,
                task_id=task_id,
                worker_id=worker_id,
            )
        ).result())

    def execute_batch_chunk(
            self,
            *,
            batch_id: str,
            shard_id: str,
            start_index: int,
            end_index: int,
            worker_id: str | None = None,
    ) -> None:
        """执行批次的半开区间分片

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）
            worker_id: 当前 Celery Worker 标识（可选）
        """
        self._submit(
            self._execute_batch_chunk(
                batch_id=batch_id,
                shard_id=shard_id,
                start_index=start_index,
                end_index=end_index,
                worker_id=worker_id,
            )
        ).result()

    def mark_batch_chunk_failed(
            self,
            *,
            batch_id: str,
            shard_id: str,
            start_index: int,
            end_index: int,
            error: str,
    ) -> None:
        """将重试耗尽的分片标记失败并尝试汇总

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）
            error: 分片执行失败原因
        """
        self._submit(
            self._mark_batch_chunk_failed(
                batch_id=batch_id,
                shard_id=shard_id,
                start_index=start_index,
                end_index=end_index,
                error=error,
            )
        ).result()

    def register_batch_shards(
            self,
            *,
            batch_id: str,
            shards: list[dict[str, object]],
    ) -> None:
        """在发布消息前登记本次执行的全部分片

        参数：
            batch_id: 批次 ID
            shards: 待登记的分片计划
        """
        self._submit(
            self._register_batch_shards(batch_id=batch_id, shards=shards)
        ).result()

    def mark_batch_chunk_retrying(
            self,
            *,
            shard_id: str,
            error: str,
    ) -> None:
        """记录分片等待 Celery 独立重试

        参数：
            shard_id: 分片 ID
            error: 本次分片执行失败原因
        """
        self._submit(
            self._mark_batch_chunk_retrying(shard_id=shard_id, error=error)
        ).result()

    def execute_shadow(self, *, execution_id: str) -> None:
        """执行持久化影子预测任务

        参数：
            execution_id: 影子执行 ID
        """
        self._submit(
            self._execute_shadow(execution_id)
        ).result()

    def mark_batch_failed(self, *, batch_id: str, error: str) -> None:
        """记录批次执行失败

        参数：
            batch_id: 批次 ID
            error: 失败原因
        """
        self._submit(
            self._mark_batch_failed(
                batch_id=batch_id,
                error=error,
            )
        ).result()

    def mark_batch_retrying(
            self,
            *,
            batch_id: str,
            error: str,
            retry_in_seconds: int,
    ) -> None:
        """标记批次等待自动重试

        参数：
            batch_id: 批次 ID
            error: 本次执行失败原因
            retry_in_seconds: 距离下一次重试的秒数
        """
        self._submit(
            self._mark_batch_retrying(
                batch_id=batch_id,
                error=error,
                retry_in_seconds=retry_in_seconds,
            )
        ).result()

    def requeue_shadow(self, execution_id: str) -> None:
        """将待重试影子执行恢复为等待状态

        参数：
            execution_id: 影子执行 ID
        """
        self._submit(
            self._service.reset_shadow_for_retry(execution_id)
        ).result()

    def shutdown(self) -> None:
        """关闭运行时服务并停止专用事件循环"""
        loop = self._loop
        if loop is None or not loop.is_running():
            return

        future = asyncio.run_coroutine_threadsafe(
            self._service.shutdown(),
            loop,
        )
        future.result(timeout=30)
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=30)

    def _run_loop(self) -> None:
        """在线程中初始化运行时服务并运行事件循环"""
        from datamind.runtime.server.service import DatamindRuntimeService

        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        try:
            service_class = getattr(
                DatamindRuntimeService,
                "inner",
            )
            self._service = service_class()
            loop.run_until_complete(self._service.startup())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            loop.close()
            return

        self._ready.set()

        try:
            loop.run_forever()
        finally:
            loop.close()

    def _submit(
            self,
            coroutine: Coroutine[Any, Any, Any],
    ) -> Future[Any]:
        """向专用事件循环提交协程

        参数：
            coroutine: 待执行协程

        返回：
            可由同步 Celery 任务等待的 Future

        异常：
            RuntimeError: 专用事件循环尚未启动
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            coroutine.close()
            raise RuntimeError("Celery 运行时尚未启动")

        return asyncio.run_coroutine_threadsafe(coroutine, loop)

    async def _prepare_batch(
            self,
            *,
            batch_id: str,
            task_id: str,
            worker_id: str | None = None,
    ) -> int:
        """锁定批次、启动尝试并一次性创建请求记录

        参数：
            batch_id: 批次 ID
            task_id: 当前 Celery 任务 ID
            worker_id: 当前 Celery Worker 标识（可选）

        返回：
            批次包含的请求记录数量；批次无需执行时返回 0
        """
        async with UnitOfWork() as batch_uow:
            batch = await BatchRepository(batch_uow.session).start(
                batch_id=batch_id,
                task_id=task_id,
            )

            if batch is None:
                return 0

            await AttemptRepository(batch_uow.session).mark_started(
                batch_id=batch_id,
                task_id=task_id,
                attempt_number=batch.attempt_count,
                worker_id=worker_id,
            )

            request = BatchPredictRequest.model_validate(batch.payload)
            user = batch.user or "system"
            ip = batch.ip

        with context_scope(
                trace_id=generate_trace_id(),
                request_id=batch_id,
                source="worker",
                user=user,
                ip=ip,
                hostname=None,
        ):
            return await self._service.prepare_batch_task(
                request=request,
                batch_id=batch_id,
            )

    async def _execute_batch_chunk(
            self,
            *,
            batch_id: str,
            shard_id: str,
            start_index: int,
            end_index: int,
            worker_id: str | None = None,
    ) -> None:
        """执行单个分片并在全部分片完成后汇总批次

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）
            worker_id: 当前 Celery Worker 标识（可选）

        异常：
            ValueError: 分片范围无效
        """
        async with UnitOfWork() as shard_uow:
            shard = await ShardRepository(shard_uow.session).mark_started(
                shard_id=shard_id,
                worker_id=worker_id,
            )
            if shard is None or shard.status in {
                "succeeded", "partially_succeeded", "failed", "cancelled",
            }:
                return
        async with UnitOfWork() as batch_uow:
            batch = await BatchRepository(batch_uow.session).get_batch(
                batch_id
            )
            if batch is None or batch.status not in {"running", "cancelling"}:
                return
            request = BatchPredictRequest.model_validate(batch.payload)
            user = batch.user or "system"
            ip = batch.ip

        if (
                start_index < 0
                or end_index <= start_index
                or end_index > len(request.instances)
        ):
            raise ValueError("批量分片范围无效")

        async def cancel_check() -> bool:
            async with UnitOfWork() as cancel_uow:
                return await BatchRepository(
                    cancel_uow.session
                ).is_cancel_requested(batch_id)

        with context_scope(
                trace_id=generate_trace_id(),
                request_id=batch_id,
                source="worker",
                user=user,
                ip=ip,
                hostname=None,
        ):
            try:
                await self._service.execute_batch_task(
                    request=request,
                    batch_id=batch_id,
                    batch_indices=list(range(start_index, end_index)),
                    prepare_records=False,
                    cancel_check=cancel_check,
                    raise_errors=True,
                )
            except BatchCancelledError:
                async with UnitOfWork() as shard_uow:
                    await ShardRepository(shard_uow.session).mark_finished(
                        shard_id=shard_id,
                        status="cancelled",
                    )
            else:
                await self._finish_batch_chunk(
                    batch_id=batch_id,
                    shard_id=shard_id,
                    start_index=start_index,
                    end_index=end_index,
                )

        await self._finalize_batch_if_complete(batch_id)

    async def _mark_batch_chunk_failed(
            self,
            *,
            batch_id: str,
            shard_id: str,
            start_index: int,
            end_index: int,
            error: str,
    ) -> None:
        """将分片中仍未成功的请求置为失败

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）
            error: 分片执行失败原因
        """
        async with UnitOfWork() as uow:
            repository = RequestRepository(uow.session)
            records = await repository.list_batch_requests(batch_id)
            for record in records:
                if (
                        record.batch_index is not None
                        and start_index <= record.batch_index < end_index
                        and record.status != "success"
                ):
                    repository.mark_failed(record, error=error)
            await ShardRepository(uow.session).mark_finished(
                shard_id=shard_id,
                status="failed",
                error=error,
            )
        await self._finalize_batch_if_complete(batch_id)

    @staticmethod
    async def _register_batch_shards(
            *,
            batch_id: str,
            shards: list[dict[str, object]],
    ) -> None:
        """将协调任务生成的分片计划持久化

        参数：
            batch_id: 批次 ID
            shards: 待持久化的分片计划

        异常：
            RuntimeError: 批次执行尝试不存在
        """
        async with UnitOfWork() as uow:
            attempt = await AttemptRepository(
                uow.session
            ).get_latest_attempt(batch_id)
            if attempt is None:
                raise RuntimeError(f"批次执行尝试不存在: {batch_id}")
            repository = ShardRepository(uow.session)
            for shard in shards:
                repository.create_shard(
                    shard_id=cast(str, shard["shard_id"]),
                    attempt_id=attempt.attempt_id,
                    batch_id=batch_id,
                    task_id=cast(str, shard["task_id"]),
                    start_index=cast(int, shard["start_index"]),
                    end_index=cast(int, shard["end_index"]),
                )

    @staticmethod
    async def _mark_batch_chunk_retrying(
            *,
            shard_id: str,
            error: str,
    ) -> None:
        """记录分片等待 Celery 独立重试

        参数：
            shard_id: 分片 ID
            error: 本次分片执行失败原因
        """
        async with UnitOfWork() as uow:
            await ShardRepository(uow.session).mark_retrying(
                shard_id=shard_id,
                error=error,
            )

    @staticmethod
    async def _finish_batch_chunk(
            *,
            batch_id: str,
            shard_id: str,
            start_index: int,
            end_index: int,
    ) -> None:
        """根据分片内逐条请求结果确定分片终态

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）
        """
        async with UnitOfWork() as uow:
            records = await RequestRepository(uow.session).list_batch_requests(
                batch_id
            )
            selected = [
                record for record in records
                if record.batch_index is not None
                and start_index <= record.batch_index < end_index
            ]
            succeeded = sum(record.status == "success" for record in selected)
            failed = sum(record.status == "failed" for record in selected)
            expected = end_index - start_index
            if succeeded == expected:
                status = "succeeded"
            elif succeeded > 0 and succeeded + failed == expected:
                status = "partially_succeeded"
            else:
                status = "failed"
            await ShardRepository(uow.session).mark_finished(
                shard_id=shard_id,
                status=status,
                error="分片预测失败" if status == "failed" else None,
            )

    async def _finalize_batch_if_complete(self, batch_id: str) -> None:
        """在数据库锁内更新进度并由最后一个分片写入终态

        参数：
            batch_id: 批次 ID
        """
        async with UnitOfWork() as uow:
            repository = BatchRepository(uow.session)
            batch = await repository.get_batch(batch_id, for_update=True)
            if batch is None or batch.status not in {"running", "cancelling"}:
                return

            result, succeeded_count, failed_count = (
                await self._build_batch_result(uow.session, batch_id)
            )
            completed_count = succeeded_count + failed_count
            batch.completed_count = completed_count
            batch.succeeded_count = succeeded_count
            batch.failed_count = failed_count

            if completed_count < batch.total_count:
                return

            if batch.status == "cancelling":
                await repository.mark_cancelled(
                    batch_id=batch_id,
                    result=result,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                )
                attempt_status = "cancelled"
            elif failed_count == 0:
                await repository.mark_succeeded(
                    batch_id=batch_id,
                    result=result,
                )
                attempt_status = "succeeded"
            elif succeeded_count > 0:
                await repository.mark_partially_succeeded(
                    batch_id=batch_id,
                    result=result,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                )
                attempt_status = "partially_succeeded"
            else:
                await repository.mark_failed(
                    batch_id=batch_id,
                    error="批量预测失败",
                    result=result,
                )
                attempt_status = "failed"

            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status=attempt_status,
                error=(
                    "批量预测失败"
                    if attempt_status == "failed"
                    else None
                ),
            )

    async def _execute_shadow(self, execution_id: str) -> None:
        """加载并执行影子预测任务"""
        task = await self._service.load_shadow_task(execution_id)
        if task is None:
            return

        with context_scope(
                trace_id=generate_trace_id(),
                request_id=task.request_id,
                source="worker",
                user="system",
                ip=None,
                hostname=None,
        ):
            await self._service.execute_shadow_task(
                task,
                raise_errors=True,
            )

    @staticmethod
    async def _mark_batch_retrying(
            *,
            batch_id: str,
            error: str,
            retry_in_seconds: int,
    ) -> None:
        """记录批次即将由 Celery 重试"""
        async with UnitOfWork() as uow:
            await BatchRepository(uow.session).mark_retrying(
                batch_id,
                error=error,
            )
            await AttemptRepository(
                uow.session
            ).mark_retry_scheduled(
                batch_id=batch_id,
                error=error,
                retry_in_seconds=retry_in_seconds,
            )

    @staticmethod
    async def _mark_batch_failed(
            *,
            batch_id: str,
            error: str,
    ) -> None:
        """根据逐条执行结果持久化批次失败状态"""
        async with UnitOfWork() as uow:
            result, succeeded_count, failed_count = (
                await RuntimeTaskWorker._build_batch_result(
                    uow.session,
                    batch_id,
                )
            )
            repository = BatchRepository(uow.session)
            await ShardRepository(uow.session).mark_open_shards_failed(
                batch_id=batch_id,
                error=error,
            )

            if succeeded_count > 0 and failed_count > 0:
                await repository.mark_partially_succeeded(
                    batch_id=batch_id,
                    result=result,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                )
            else:
                await repository.mark_failed(
                    batch_id=batch_id,
                    error=error,
                    result=result,
                )
            await AttemptRepository(uow.session).mark_finished(
                batch_id=batch_id,
                status=(
                    "partially_succeeded"
                    if succeeded_count > 0 and failed_count > 0
                    else "failed"
                ),
                error=error,
            )

    @staticmethod
    async def _build_batch_result(
            session: Any,
            batch_id: str,
    ) -> tuple[dict[str, Any], int, int]:
        """根据逐条请求记录构造批次执行结果

        参数：
            session: 数据库会话
            batch_id: 批次 ID

        返回：
            批次响应、成功条目数和失败条目数
        """
        records = await RequestRepository(
            session
        ).list_batch_requests(batch_id)
        responses = [
            record.response
            for record in records
            if isinstance(record.response, dict)
        ]
        succeeded_count = sum(
            record.status == "success"
            for record in records
        )
        failed_count = sum(
            record.status == "failed"
            for record in records
        )
        return (
            {
                "success": failed_count == 0,
                "count": len(responses),
                "succeeded_count": succeeded_count,
                "failed_count": failed_count,
                "predictions": responses,
                "batch_id": batch_id,
            },
            succeeded_count,
            failed_count,
        )


_worker: RuntimeTaskWorker | None = None
_worker_lock = threading.Lock()


def get_runtime_task_worker() -> RuntimeTaskWorker:
    """获取当前 Celery 子进程的运行时执行器

    返回：
        当前进程共享的运行时任务执行器
    """
    global _worker

    worker = _worker
    if worker is not None:
        return worker

    with _worker_lock:
        worker = _worker
        if worker is None:
            worker = RuntimeTaskWorker()
            _worker = worker

        return worker


def shutdown_runtime_task_worker() -> None:
    """关闭并释放当前 Celery 子进程的运行时执行器"""
    global _worker

    worker = _worker
    _worker = None

    if worker is not None:
        worker.shutdown()
