"""运行时任务发布器测试.

验证批量预测和影子预测任务的队列发布与撤销委托行为。

核心功能：
  - test_submit_batch_uses_batch_queue:
    验证批量预测任务发布到批次队列
  - test_submit_shadow_uses_shadow_queue:
    验证影子预测任务发布到影子队列
  - test_revoke_delegates_to_celery_control:
    验证任务撤销委托给 Celery 控制面
  - test_submit_batch_chunk_uses_batch_queue:
    测试批量分片带全局下标范围发布
"""

from unittest.mock import MagicMock, patch

import datamind.runtime.task_queue.publisher as publisher_module
from datamind.config.queue import TaskQueueConfig
from datamind.runtime.task_queue.publisher import (
    BATCH_CHUNK_TASK_NAME,
    BATCH_TASK_NAME,
    SHADOW_TASK_NAME,
    TaskPublisher,
)


def test_submit_batch_uses_batch_queue() -> None:
    """测试批量预测只发布引用标识到批次队列."""
    config = TaskQueueConfig()

    celery_app = MagicMock()
    with patch.dict(
        vars(publisher_module),
        {"celery_app": celery_app},
    ):
        TaskPublisher().submit_batch(
            batch_id="bat_test",
            task_id="tsk_batch",
        )

    celery_app.send_task.assert_called_once_with(
        BATCH_TASK_NAME,
        kwargs={"batch_id": "bat_test"},
        task_id="tsk_batch",
        queue=config.batch_queue,
    )


def test_submit_shadow_uses_shadow_queue() -> None:
    """测试影子预测只发布执行 ID 到影子队列."""
    config = TaskQueueConfig()

    celery_app = MagicMock()
    with patch.dict(
        vars(publisher_module),
        {"celery_app": celery_app},
    ):
        TaskPublisher().submit_shadow(
            execution_id="exe_test",
            task_id="tsk_shadow",
        )

    celery_app.send_task.assert_called_once_with(
        SHADOW_TASK_NAME,
        kwargs={"execution_id": "exe_test"},
        task_id="tsk_shadow",
        queue=config.shadow_queue,
    )


def test_submit_batch_chunk_uses_batch_queue() -> None:
    """测试批量分片带全局下标范围发布."""
    config = TaskQueueConfig()
    celery_app = MagicMock()
    with patch.dict(vars(publisher_module), {"celery_app": celery_app}):
        TaskPublisher().submit_batch_chunk(
            batch_id="bat_test",
            shard_id="shd_test",
            task_id="tsk_chunk",
            start_index=20,
            end_index=40,
        )

    celery_app.send_task.assert_called_once_with(
        BATCH_CHUNK_TASK_NAME,
        kwargs={
            "batch_id": "bat_test",
            "shard_id": "shd_test",
            "start_index": 20,
            "end_index": 40,
        },
        task_id="tsk_chunk",
        queue=config.batch_queue,
    )


def test_revoke_delegates_to_celery_control() -> None:
    """测试撤销请求委托给 Celery 控制面."""
    celery_app = MagicMock()
    with patch.dict(
        vars(publisher_module),
        {"celery_app": celery_app},
    ):
        TaskPublisher.revoke("tsk_test")

    celery_app.control.revoke.assert_called_once_with(
        "tsk_test"
    )
