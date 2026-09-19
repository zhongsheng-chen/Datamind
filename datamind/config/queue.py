"""异步任务队列配置

定义 Celery Broker、批量预测队列和影子预测队列参数。

核心功能：
  - TaskQueueConfig: 读取并校验异步任务队列配置

属性：
  - broker_url: Celery Broker 连接 URL
  - batch_queue: 批量预测任务队列名称
  - shadow_queue: 影子预测任务队列名称
  - max_retries: 任务最大重试次数
  - batch_chunk_size: 单个批量分片包含的请求数
  - retry_backoff_seconds: 任务重试退避基数（秒）
  - visibility_timeout_seconds: Broker 消息可见性超时时间（秒）

环境变量：
  - DATAMIND_TASK_QUEUE_BROKER_URL:
    Broker 连接 URL，默认 redis://localhost:6379/0
  - DATAMIND_TASK_QUEUE_BATCH_QUEUE:
    批量预测队列名称，默认 prediction.batch
  - DATAMIND_TASK_QUEUE_SHADOW_QUEUE:
    影子预测队列名称，默认 prediction.shadow
  - DATAMIND_TASK_QUEUE_MAX_RETRIES:
    最大重试次数，默认 3
  - DATAMIND_TASK_QUEUE_BATCH_CHUNK_SIZE:
    批量分片大小，默认 20
  - DATAMIND_TASK_QUEUE_RETRY_BACKOFF_SECONDS:
    重试退避基数，默认 5
  - DATAMIND_TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS:
    消息可见性超时，默认 3600

使用示例：
  from datamind.config.queue import TaskQueueConfig

  config = TaskQueueConfig()

  print(config.broker_url)
  print(config.batch_queue)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class TaskQueueConfig(BaseSettings):
    """异步任务队列配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_TASK_QUEUE_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    broker_url: str = "redis://localhost:6379/0"
    batch_queue: str = "prediction.batch"
    shadow_queue: str = "prediction.shadow"
    max_retries: int = 3
    batch_chunk_size: int = 20
    retry_backoff_seconds: int = 5
    visibility_timeout_seconds: int = 3600

    @model_validator(mode="after")
    def validate_config(self) -> "TaskQueueConfig":
        """校验异步任务队列配置参数"""
        if not self.broker_url.strip():
            raise ValueError("broker_url 不能为空")

        if not self.batch_queue.strip():
            raise ValueError("batch_queue 不能为空")

        if not self.shadow_queue.strip():
            raise ValueError("shadow_queue 不能为空")

        if self.batch_queue == self.shadow_queue:
            raise ValueError("批量预测和影子预测必须使用不同队列")

        if self.max_retries < 0:
            raise ValueError("max_retries 不能小于 0")

        if self.batch_chunk_size < 1:
            raise ValueError("batch_chunk_size 必须大于等于 1")

        if self.retry_backoff_seconds < 1:
            raise ValueError("retry_backoff_seconds 必须大于等于 1")

        if self.visibility_timeout_seconds < 1:
            raise ValueError("visibility_timeout_seconds 必须大于等于 1")

        return self
