"""异步任务 Worker 配置.

定义异步任务 Worker 的进程运行参数。

核心功能：
  - TaskWorkerConfig: 读取并校验异步任务 Worker 配置

属性：
  - name: Worker 名称
  - role: Worker 处理的任务类型
  - concurrency: Worker 并发数
  - log_level: Worker 日志级别

环境变量：
  - DATAMIND_TASK_WORKER_NAME:
    Worker 名称，默认 datamind-task-worker
  - DATAMIND_TASK_WORKER_ROLE:
    Worker 处理的任务类型，默认 all
  - DATAMIND_TASK_WORKER_CONCURRENCY:
    Worker 并发数，默认 1
  - DATAMIND_TASK_WORKER_LOG_LEVEL:
    Worker 日志级别，默认 INFO

使用示例：
  from datamind.config.worker import TaskWorkerConfig

  config = TaskWorkerConfig()

  print(config.name)
  print(config.role)
"""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from datamind.constants import LogLevel


class TaskWorkerConfig(BaseSettings):
    """异步任务 Worker 进程配置."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_TASK_WORKER_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    name: str = "datamind-task-worker"
    role: Literal["all", "batch", "shadow"] = "all"
    concurrency: int = 1
    log_level: LogLevel = LogLevel.INFO

    @model_validator(mode="after")
    def validate_config(self) -> "TaskWorkerConfig":
        """校验 Worker 进程参数."""
        if not self.name.strip():
            raise ValueError("name 不能为空")

        if "@" in self.name:
            raise ValueError("name 不能包含 @")

        if self.concurrency < 1:
            raise ValueError("concurrency 必须大于等于 1")

        return self
