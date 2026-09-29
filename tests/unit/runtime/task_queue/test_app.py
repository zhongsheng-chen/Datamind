"""运行时 Celery 应用测试.

验证 Celery 应用的 Broker、消息可靠性、任务队列和路由配置。

核心功能：
  - test_task_queue_app_imports_without_database_configuration:
    验证模块导入不依赖数据库配置
  - test_task_queue_tasks_import_without_database_configuration:
    验证任务入口导入不连带初始化运行时服务
  - test_create_celery_app_uses_explicit_task_queue_config:
    验证 Celery 应用工厂支持显式任务队列配置
  - test_celery_app_uses_task_queue_config:
    验证 Celery 应用使用任务队列配置
  - test_celery_app_configures_reliable_json_messages:
    验证 Celery 应用配置可靠的 JSON 消息
  - test_celery_app_isolates_runtime_task_queues:
    验证批量预测与影子预测使用独立队列
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from datamind.config.queue import TaskQueueConfig

from datamind.runtime.task_queue.app import (
    celery_app,
    create_celery_app,
    task_queue_config,
)


def test_task_queue_app_imports_without_database_configuration(
    tmp_path: Path,
) -> None:
    """测试 Celery 应用模块导入不需要数据库配置."""
    environment = os.environ.copy()
    environment.pop("DATAMIND_DATABASE_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from datamind.runtime.task_queue.app import celery_app; "
                "print(celery_app.main)"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "datamind_runtime"


def test_task_queue_tasks_import_without_database_configuration(
    tmp_path: Path,
) -> None:
    """测试 Celery 任务入口导入不需要数据库配置."""
    environment = os.environ.copy()
    environment.pop("DATAMIND_DATABASE_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import datamind.runtime.task_queue.tasks; print('imported')",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "imported"


def test_create_celery_app_uses_explicit_task_queue_config() -> None:
    """测试 Celery 应用工厂使用显式任务队列配置."""
    config = TaskQueueConfig(
        broker_url="redis://queue.test:6379/7",
        batch_queue="test.batch",
        shadow_queue="test.shadow",
        visibility_timeout_seconds=900,
    )

    app = create_celery_app(config)

    assert app.conf.broker_url == config.broker_url
    assert app.conf.broker_transport_options == {
        "visibility_timeout": config.visibility_timeout_seconds
    }
    assert {
        queue.name
        for queue in app.conf.task_queues
    } == {
        config.batch_queue,
        config.shadow_queue,
    }


def test_celery_app_uses_task_queue_config() -> None:
    """测试 Celery 应用使用任务队列配置."""
    assert celery_app.main == "datamind_runtime"
    assert celery_app.conf.broker_url == (
        task_queue_config.broker_url
    )
    assert celery_app.conf.include == [
        "datamind.runtime.task_queue.tasks"
    ]


def test_celery_app_configures_reliable_json_messages() -> None:
    """测试 Celery 应用配置可靠的 JSON 消息."""
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.task_ignore_result is True
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert (
        celery_app.conf.broker_connection_retry_on_startup
        is True
    )
    assert celery_app.conf.broker_transport_options == {
        "visibility_timeout": (
            task_queue_config.visibility_timeout_seconds
        )
    }


def test_celery_app_isolates_runtime_task_queues() -> None:
    """测试批量预测与影子预测使用独立队列."""
    task_queues = celery_app.conf.task_queues

    assert task_queues is not None
    assert {
        queue.name
        for queue in task_queues
    } == {
        task_queue_config.batch_queue,
        task_queue_config.shadow_queue,
    }
    assert celery_app.conf.task_routes == {
        "datamind.prediction.batch.execute": {
            "queue": task_queue_config.batch_queue,
        },
        "datamind.prediction.batch.chunk.execute": {
            "queue": task_queue_config.batch_queue,
        },
        "datamind.prediction.shadow.execute": {
            "queue": task_queue_config.shadow_queue,
        },
    }
