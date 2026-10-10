"""启动任务 Worker 命令.

提供任务 Worker 启动功能。

核心功能：
  - run_worker: 启动任务 Worker

使用示例：
  python -m datamind.cli.main worker run \
    --role batch \
    --concurrency 4
"""

from enum import Enum

import typer

from datamind.config import get_task_worker_config
from datamind.config.worker import TaskWorkerConfig


class WorkerRole(str, Enum):
    """任务 Worker 支持的任务类型."""

    ALL = "all"
    BATCH = "batch"
    SHADOW = "shadow"


app = typer.Typer(
    help="启动任务 Worker 命令"
)


@app.command("run")
def run_worker(
        role: WorkerRole | None = typer.Option(
            None,
            "--role",
            help="处理的任务类型，默认使用配置值",
        ),
        concurrency: int | None = typer.Option(
            None,
            "--concurrency",
            min=1,
            help="Worker 并发数，默认使用配置值",
        ),
) -> None:
    """启动任务 Worker."""
    from datamind.runtime.task_queue.entrypoints.worker import main

    config_values = get_task_worker_config().model_dump()

    if role is not None:
        config_values["role"] = role.value

    if concurrency is not None:
        config_values["concurrency"] = concurrency

    worker_config = TaskWorkerConfig.model_validate(config_values)
    main(worker_config)
