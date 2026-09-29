"""运行时 Celery 任务.

定义批量预测和影子预测的 Celery 任务入口，将执行工作交给
进程内运行时执行器，并按指数退避策略重试瞬时异常。

核心功能：
  - execute_batch: 执行持久化批量预测任务
  - execute_batch_chunk: 执行批量预测分片任务
  - execute_shadow: 执行持久化影子预测任务

使用示例：
  from datamind.runtime.task_queue.tasks import execute_batch

  execute_batch.delay(
      batch_id="bat_0123456789abcdef",
  )
"""

from typing import cast

from celery.signals import worker_process_shutdown

from datamind.config import get_task_queue_config
from datamind.runtime.task_queue.app import celery_app
from datamind.runtime.task_queue.publisher import TaskPublisher
from datamind.runtime.task_queue.worker import (
    get_runtime_task_worker,
    shutdown_runtime_task_worker,
)
from datamind.utils.generator import generate_random_id


def _retry_countdown(retries: int) -> int:
    """计算下一次任务重试的等待时间.

    参数：
        retries: 当前已重试次数

    返回：
        按指数退避计算且不超过 300 秒的等待时间
    """
    config = get_task_queue_config()
    return min(
        config.retry_backoff_seconds * (2 ** retries),
        300,
    )


@celery_app.task(
    bind=True,
    name="datamind.prediction.batch.execute",
)
def execute_batch(self, *, batch_id: str) -> None:
    """准备持久化批次并发布可并行消费的分片任务.

    参数：
        batch_id: 批次 ID
    """
    worker = get_runtime_task_worker()
    config = get_task_queue_config()
    task_id = str(self.request.id)

    try:
        total_count = worker.prepare_batch(
            batch_id=batch_id,
            task_id=task_id,
            worker_id=(
                str(self.request.hostname)
                if self.request.hostname
                else None
            ),
        )
        if total_count == 0:
            return

        chunk_size = config.batch_chunk_size
        publisher = TaskPublisher()
        chunks: list[dict[str, object]] = []
        for start_index in range(0, total_count, chunk_size):
            end_index = min(start_index + chunk_size, total_count)
            chunks.append({
                "shard_id": generate_random_id(prefix="shd"),
                "task_id": generate_random_id(prefix="tsk"),
                "start_index": start_index,
                "end_index": end_index,
            })
        worker.register_batch_shards(batch_id=batch_id, shards=chunks)
        for chunk in chunks:
            publisher.submit_batch_chunk(
                batch_id=batch_id,
                shard_id=cast(str, chunk["shard_id"]),
                task_id=cast(str, chunk["task_id"]),
                start_index=cast(int, chunk["start_index"]),
                end_index=cast(int, chunk["end_index"]),
            )
    except Exception as exc:
        worker.mark_batch_failed(
            batch_id=batch_id,
            error=str(exc) or exc.__class__.__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="datamind.prediction.batch.chunk.execute",
)
def execute_batch_chunk(
        self,
        *,
        batch_id: str,
        shard_id: str,
        start_index: int,
        end_index: int,
) -> None:
    """执行批量预测分片任务.

    执行异常未超过重试上限时独立重试当前分片；
    重试耗尽后记录分片失败并继续抛出异常。

    参数：
        batch_id: 批次 ID
        shard_id: 分片 ID
        start_index: 分片起始位置（包含）
        end_index: 分片结束位置（不包含）
    """
    worker = get_runtime_task_worker()
    config = get_task_queue_config()
    try:
        worker.execute_batch_chunk(
            batch_id=batch_id,
            shard_id=shard_id,
            start_index=start_index,
            end_index=end_index,
            worker_id=(
                str(self.request.hostname)
                if self.request.hostname
                else None
            ),
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        if self.request.retries < config.max_retries:
            worker.mark_batch_chunk_retrying(shard_id=shard_id, error=error)
            raise self.retry(
                exc=exc,
                countdown=_retry_countdown(self.request.retries),
                max_retries=config.max_retries,
            )
        worker.mark_batch_chunk_failed(
            batch_id=batch_id,
            shard_id=shard_id,
            start_index=start_index,
            end_index=end_index,
            error=error,
        )
        raise


@celery_app.task(
    bind=True,
    name="datamind.prediction.shadow.execute",
)
def execute_shadow(self, *, execution_id: str) -> None:
    """执行持久化影子预测任务.

    执行异常未超过重试上限时恢复影子执行等待状态并交由
    Celery 延迟重试；重试耗尽后继续抛出异常。

    参数：
        execution_id: 影子执行 ID
    """
    worker = get_runtime_task_worker()
    config = get_task_queue_config()

    try:
        worker.execute_shadow(execution_id=execution_id)
    except Exception as exc:
        if self.request.retries < config.max_retries:
            worker.requeue_shadow(execution_id)
            raise self.retry(
                exc=exc,
                countdown=_retry_countdown(self.request.retries),
                max_retries=config.max_retries,
            )
        raise


@worker_process_shutdown.connect
def _shutdown_worker(**_kwargs: object) -> None:
    """在 Celery 子进程退出前关闭运行时执行器."""
    shutdown_runtime_task_worker()
