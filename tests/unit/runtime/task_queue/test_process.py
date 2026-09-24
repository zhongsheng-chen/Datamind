"""Celery Worker 进程入口测试.

验证 Worker 启动参数构建和进程启动行为。

核心功能：
  - test_build_worker_arguments_uses_queue_config:
    验证启动参数使用统一任务队列配置
  - test_build_worker_arguments_uses_solo_pool_on_windows:
    验证 Windows 平台使用 solo 进程池
  - test_build_worker_arguments_supports_dedicated_roles:
    验证专用 Worker 角色仅消费对应队列
  - test_main_starts_celery_worker:
    验证进程入口使用构建后的参数启动 Celery Worker
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import datamind.runtime.task_queue.entrypoints.worker as process_module


def replace_process_dependency(
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        replacement: object,
) -> None:
    """替换进程入口依赖并在测试结束后自动恢复."""
    monkeypatch.setattr(process_module, name, replacement)


def replace_celery_method(
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        replacement: object,
) -> None:
    """替换 Celery 应用接口并在测试结束后自动恢复."""
    monkeypatch.setattr(process_module.celery_app, name, replacement)


def test_build_worker_arguments_uses_queue_config(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Worker 启动参数来自统一任务队列配置."""
    queue_config = SimpleNamespace(
        batch_queue="batch-test",
        shadow_queue="shadow-test",
    )
    worker_config = SimpleNamespace(
        name="worker-test",
        role="all",
        concurrency=3,
        log_level="WARNING",
    )
    replace_process_dependency(
        monkeypatch,
        "get_task_queue_config",
        lambda: queue_config,
    )
    replace_process_dependency(
        monkeypatch,
        "get_task_worker_config",
        lambda: worker_config,
    )
    monkeypatch.setattr(process_module.sys, "platform", "linux")
    monkeypatch.setattr(process_module.os, "getpid", lambda: 4321)

    assert process_module.build_worker_arguments() == [
        "worker",
        "--hostname",
        "worker-test-4321@%h",
        "--queues",
        "batch-test,shadow-test",
        "--concurrency",
        "3",
        "--loglevel",
        "WARNING",
    ]


def test_build_worker_arguments_uses_solo_pool_on_windows(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Windows Worker 使用 Celery 支持的 solo 进程池."""
    monkeypatch.setattr(process_module.sys, "platform", "win32")

    arguments = process_module.build_worker_arguments()

    assert arguments[-2:] == ["--pool", "solo"]


@pytest.mark.parametrize(
    ("role", "expected_queue"),
    [
        ("batch", "prediction.batch"),
        ("shadow", "prediction.shadow"),
    ],
)
def test_build_worker_arguments_supports_dedicated_roles(
        monkeypatch: pytest.MonkeyPatch,
        role: str,
        expected_queue: str,
) -> None:
    """测试专用 Worker 角色仅消费对应队列."""
    queue_config = SimpleNamespace(
        batch_queue="prediction.batch",
        shadow_queue="prediction.shadow",
    )
    worker_config = SimpleNamespace(
        name="worker-test",
        role=role,
        concurrency=1,
        log_level="INFO",
    )
    replace_process_dependency(
        monkeypatch,
        "get_task_queue_config",
        lambda: queue_config,
    )
    replace_process_dependency(
        monkeypatch,
        "get_task_worker_config",
        lambda: worker_config,
    )
    arguments = process_module.build_worker_arguments()
    queue_index = arguments.index("--queues") + 1
    assert arguments[queue_index] == expected_queue


def test_main_starts_celery_worker(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试进程入口使用构建后的参数启动 Celery Worker."""
    arguments = ["worker", "--queues", "batch"]
    build_arguments = MagicMock(return_value=arguments)
    worker_main = MagicMock()
    replace_process_dependency(
        monkeypatch,
        "build_worker_arguments",
        build_arguments,
    )
    replace_celery_method(
        monkeypatch,
        "worker_main",
        worker_main,
    )

    process_module.main()

    worker_main.assert_called_once_with(arguments)
