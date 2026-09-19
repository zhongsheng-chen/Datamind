"""运行时 Celery 应用

定义运行时异步任务的 Celery 应用，配置 Redis Broker、消息可靠性
和队列路由。批量预测与影子预测使用不同队列，执行状态及结果由
PostgreSQL 持久化。

核心功能：
  - create_celery_app: 根据任务队列配置创建 Celery 应用
  - celery_app: 发布并执行运行时异步任务的 Celery 应用

使用示例：
  from datamind.runtime.task_queue.app import celery_app

  print(celery_app.conf.broker_url)
"""

from celery import Celery
from kombu import Queue

from datamind.config import get_task_queue_config
from datamind.config.queue import TaskQueueConfig


def create_celery_app(
        config: TaskQueueConfig | None = None,
) -> Celery:
    """根据任务队列配置创建 Celery 应用"""
    resolved_config = config or get_task_queue_config()

    app = Celery(
        "datamind_runtime",
        broker=resolved_config.broker_url,
        include=[
            "datamind.runtime.task_queue.tasks",
        ],
    )
    app.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        broker_transport_options={
            "visibility_timeout": (
                resolved_config.visibility_timeout_seconds
            ),
        },
        task_queues=(
            Queue(resolved_config.batch_queue),
            Queue(resolved_config.shadow_queue),
        ),
        task_routes={
            "datamind.prediction.batch.execute": {
                "queue": resolved_config.batch_queue,
            },
            "datamind.prediction.batch.chunk.execute": {
                "queue": resolved_config.batch_queue,
            },
            "datamind.prediction.shadow.execute": {
                "queue": resolved_config.shadow_queue,
            },
        },
    )

    return app


task_queue_config = get_task_queue_config()
celery_app = create_celery_app(task_queue_config)
