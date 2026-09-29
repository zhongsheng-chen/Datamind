"""Celery Worker 健康检查.

检查当前容器内的 Worker 是否在线，并确认其正在消费角色要求的任务队列。

运行方式：
  python -m datamind.runtime.task_queue.entrypoints.healthcheck
"""

import socket

from celery.exceptions import CeleryError
from kombu.exceptions import KombuError

from datamind.config import (
    get_task_queue_config,
    get_task_worker_config,
)
from datamind.runtime.task_queue.app import celery_app


_INSPECT_TIMEOUT_SECONDS = 2.0


def get_worker_node_pattern() -> tuple[str, str]:
    """获取当前容器的 Worker 节点名规则.

    返回：
        Worker 节点名必须满足的前缀和主机名后缀
    """
    worker_name = get_task_worker_config().name
    return f"{worker_name}-", f"@{socket.gethostname()}"


def get_required_queues() -> set[str]:
    """获取当前 Worker 角色必须消费的队列.

    返回：
        当前 Worker 角色对应的队列名称集合
    """
    queue_config = get_task_queue_config()
    worker_config = get_task_worker_config()
    return {
        "all": {
            queue_config.batch_queue,
            queue_config.shadow_queue,
        },
        "batch": {queue_config.batch_queue},
        "shadow": {queue_config.shadow_queue},
    }[worker_config.role]


def is_worker_ready() -> bool:
    """检查当前容器的 Worker 是否就绪.

    通过 Celery 检查接口确认节点名、Ping 响应和活动队列均符合
    当前容器及 Worker 角色的要求。Broker 不可用或响应无效时返回失败。

    返回：
        Worker 在线且消费全部必需队列时返回 True，否则返回 False
    """
    node_prefix, node_suffix = get_worker_node_pattern()
    required_queues = get_required_queues()
    try:
        inspector = celery_app.control.inspect(
            timeout=_INSPECT_TIMEOUT_SECONDS,
        )
        replies = inspector.ping()
        active_queues = inspector.active_queues()
    except (
            CeleryError,
            KombuError,
            OSError,
            TypeError,
            ValueError,
    ):
        return False

    if not replies or not active_queues:
        return False

    for node_name, reply in replies.items():
        if not (
            node_name.startswith(node_prefix)
            and node_name.endswith(node_suffix)
            and isinstance(reply, dict)
            and reply.get("ok") == "pong"
        ):
            continue

        queues = active_queues.get(node_name)
        if not isinstance(queues, list):
            continue
        queue_names = {
            queue.get("name")
            for queue in queues
            if isinstance(queue, dict)
        }
        if required_queues.issubset(queue_names):
            return True

    return False


def main() -> None:
    """通过进程退出码输出健康检查结果.

    Worker 就绪时以状态码 0 退出，否则以状态码 1 退出。
    """
    raise SystemExit(0 if is_worker_ready() else 1)


if __name__ == "__main__":
    main()
