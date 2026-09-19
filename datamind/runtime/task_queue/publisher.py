"""运行时任务发布器

将持久化批次和执行记录的标识发布到对应的 Celery 队列，
并将任务发布与撤销异常转换为统一的任务队列异常。

核心功能：
  - TaskPublisher: 发布批量预测和影子预测任务并撤销待执行任务

使用示例：
  from datamind.runtime.task_queue.publisher import TaskPublisher

  publisher = TaskPublisher()
  publisher.submit_batch(
      batch_id="bat_0123456789abcdef",
      task_id="tsk_0123456789abcdef",
  )
"""

from celery.exceptions import CeleryError
from kombu.exceptions import KombuError

from datamind.config import get_task_queue_config
from datamind.runtime.task_queue.app import celery_app
from datamind.runtime.task_queue.errors import TaskDispatchError


BATCH_TASK_NAME = "datamind.prediction.batch.execute"
BATCH_CHUNK_TASK_NAME = "datamind.prediction.batch.chunk.execute"
SHADOW_TASK_NAME = "datamind.prediction.shadow.execute"


class TaskPublisher:
    """Celery 运行时任务发布器

    根据任务类型选择目标队列，仅发送持久化记录标识，
    并将 Celery 和 Broker 异常转换为统一的任务队列异常。
    """

    def submit_batch(
            self,
            *,
            batch_id: str,
            task_id: str,
    ) -> None:
        """发布批量预测任务

        参数：
            batch_id: 批次 ID
            task_id: Celery 任务 ID

        异常：
            TaskDispatchError: 任务无法发布到批量预测队列
        """
        config = get_task_queue_config()
        try:
            celery_app.send_task(
                BATCH_TASK_NAME,
                kwargs={"batch_id": batch_id},
                task_id=task_id,
                queue=config.batch_queue,
            )
        except (
                CeleryError,
                KombuError,
                OSError,
                TypeError,
                ValueError,
        ) as exc:
            raise TaskDispatchError(
                "批量预测任务发布失败"
            ) from exc

    def submit_shadow(
            self,
            *,
            execution_id: str,
            task_id: str,
    ) -> None:
        """发布影子预测任务

        参数：
            execution_id: 影子执行 ID
            task_id: Celery 任务 ID

        异常：
            TaskDispatchError: 任务无法发布到影子预测队列
        """
        config = get_task_queue_config()
        try:
            celery_app.send_task(
                SHADOW_TASK_NAME,
                kwargs={"execution_id": execution_id},
                task_id=task_id,
                queue=config.shadow_queue,
            )
        except (
                CeleryError,
                KombuError,
                OSError,
                TypeError,
                ValueError,
        ) as exc:
            raise TaskDispatchError(
                "影子预测任务发布失败"
            ) from exc

    def submit_batch_chunk(
            self,
            *,
            batch_id: str,
            shard_id: str,
            task_id: str,
            start_index: int,
            end_index: int,
    ) -> None:
        """发布批量预测分片任务

        参数：
            batch_id: 批次 ID
            shard_id: 分片 ID
            task_id: Celery 任务 ID
            start_index: 分片起始位置（包含）
            end_index: 分片结束位置（不包含）

        异常：
            TaskDispatchError: 任务无法发布到批量预测队列
        """
        config = get_task_queue_config()
        try:
            celery_app.send_task(
                BATCH_CHUNK_TASK_NAME,
                kwargs={
                    "batch_id": batch_id,
                    "shard_id": shard_id,
                    "start_index": start_index,
                    "end_index": end_index,
                },
                task_id=task_id,
                queue=config.batch_queue,
            )
        except (
                CeleryError,
                KombuError,
                OSError,
                TypeError,
                ValueError,
        ) as exc:
            raise TaskDispatchError(
                "批量预测分片任务发布失败"
            ) from exc

    @staticmethod
    def revoke(task_id: str) -> None:
        """撤销尚未开始执行的任务

        参数：
            task_id: Celery 任务 ID

        异常：
            TaskDispatchError: 撤销消息无法发布到 Broker
        """
        try:
            celery_app.control.revoke(task_id)
        except (
                CeleryError,
                KombuError,
                OSError,
                TypeError,
                ValueError,
        ) as exc:
            raise TaskDispatchError(
                "任务撤销消息发布失败"
            ) from exc
