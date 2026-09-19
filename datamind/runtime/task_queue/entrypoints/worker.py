"""Celery Worker 进程入口

读取任务队列和 Worker 配置，构建 Celery 启动参数并启动任务消费进程。

运行方式：
  python -m datamind.runtime.task_queue.entrypoints.worker
"""

import os
import sys

from datamind.config import (
    get_task_queue_config,
    get_task_worker_config,
)
from datamind.runtime.task_queue.app import celery_app


def build_worker_arguments() -> list[str]:
    """构建 Celery Worker 启动参数

    根据 Worker 角色选择批量预测队列、影子预测队列或全部队列，
    并在 Windows 平台使用 Celery 支持的 solo 进程池。

    返回：
        可直接传递给 Celery worker_main 的参数列表
    """
    queue_config = get_task_queue_config()
    worker_config = get_task_worker_config()
    queues = {
        "all": f"{queue_config.batch_queue},{queue_config.shadow_queue}",
        "batch": queue_config.batch_queue,
        "shadow": queue_config.shadow_queue,
    }[worker_config.role]
    arguments = [
        "worker",
        "--hostname",
        f"{worker_config.name}-{os.getpid()}@%h",
        "--queues",
        queues,
        "--concurrency",
        str(worker_config.concurrency),
        "--loglevel",
        worker_config.log_level,
    ]

    if sys.platform == "win32":
        arguments.extend(
            [
                "--pool",
                "solo",
            ]
        )

    return arguments


def main() -> None:
    """启动 Celery Worker 进程"""
    celery_app.worker_main(build_worker_arguments())


if __name__ == "__main__":
    main()
