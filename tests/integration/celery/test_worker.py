"""Celery Worker 真实集成测试

通过配置的 Redis broker/backend 启动真实 Worker，验证正常任务与重试任务。

核心功能：
  - test_worker_executes_a_task: 验证真实 Worker 执行任务
  - test_worker_retries_then_succeeds: 验证暂时性异常触发重试
  - test_worker_reports_failure_after_max_retries: 验证超过最大重试后报告失败
"""

from __future__ import annotations

import uuid

import pytest
from celery import Celery, Task
from celery.contrib.testing.worker import start_worker


pytestmark = pytest.mark.integration


def create_app(redis_url: str) -> Celery:
    """创建使用隔离队列的 Celery 集成测试应用"""
    app = Celery(
        f"datamind-integration-{uuid.uuid4().hex}", broker=redis_url, backend=redis_url
    )
    app.conf.update(
        task_always_eager=False, task_default_queue=f"dm-it-{uuid.uuid4().hex}"
    )
    return app


def test_worker_executes_a_task(redis_url: str) -> None:
    """测试真实 Worker 能够消费并返回任务结果"""
    app = create_app(redis_url)

    @app.task(name=f"datamind.integration.add.{uuid.uuid4().hex}")
    def add(left: int, right: int) -> int:
        return left + right

    with start_worker(app, perform_ping_check=False, concurrency=1):
        assert add.delay(20, 22).get(timeout=15) == 42


def test_worker_retries_then_succeeds(redis_url: str) -> None:
    """测试 Worker 在暂时性异常后重试并成功"""
    app = create_app(redis_url)
    attempts = {"count": 0}

    @app.task(bind=True, name=f"datamind.integration.retry.{uuid.uuid4().hex}")
    def retry_once(self: Task) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise self.retry(exc=RuntimeError("transient"), countdown=0, max_retries=1)
        return "ok"

    with start_worker(app, perform_ping_check=False, concurrency=1):
        assert retry_once.delay().get(timeout=15) == "ok"
    assert attempts["count"] == 2


def test_worker_reports_failure_after_max_retries(redis_url: str) -> None:
    """测试 Worker 超过最大重试次数后保留原始异常"""
    app = create_app(redis_url)
    attempts = {"count": 0}

    @app.task(bind=True, name=f"datamind.integration.exhausted.{uuid.uuid4().hex}")
    def always_fails(self: Task) -> None:
        attempts["count"] += 1
        raise self.retry(
            exc=RuntimeError("persistent"),
            countdown=0,
            max_retries=1,
        )

    with start_worker(app, perform_ping_check=False, concurrency=1):
        result = always_fails.delay()
        with pytest.raises(RuntimeError, match="persistent"):
            result.get(timeout=15)

    assert attempts["count"] == 2
