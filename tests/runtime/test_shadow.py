"""影子预测调度器测试

验证调度器启停、有界队列、异步消费和异常隔离行为。

核心功能：
  - test_disabled_dispatcher_rejects_tasks:
    验证已关闭的调度器拒绝任务
  - test_dispatcher_processes_submitted_task:
    验证调度器处理已提交任务
  - test_dispatcher_rejects_task_when_queue_is_full:
    验证队列已满时拒绝新任务
  - test_dispatcher_continues_after_handler_error:
    验证单个任务失败后继续处理任务
"""

import asyncio

import pytest

from datamind.models.enums import ExecutionType
from datamind.runtime.executor import ExecutionPlan
from datamind.runtime.routing import RouteResult
from datamind.runtime.shadow import (
    ShadowDispatcher,
    ShadowTask,
)


def create_task(
        request_id: str = "req_test",
) -> ShadowTask:
    """创建影子预测测试任务"""
    return ShadowTask(
        execution_id=f"exe_{request_id}",
        request_id=request_id,
        decision_id="dcs_primary",
        plan=ExecutionPlan(
            route=RouteResult(
                model_id="mdl_test",
                version_id="ver_shadow",
                deployment_id="dep_shadow",
                framework="sklearn",
                environment="testing",
                source="shadow",
                strategy="weighted",
            ),
            execution_type=ExecutionType.SHADOW,
        ),
        features={"age": 35},
    )


@pytest.mark.asyncio
async def test_disabled_dispatcher_rejects_tasks() -> None:
    """测试关闭影子预测时不启动也不接收任务"""
    async def handler(_task: ShadowTask) -> None:
        raise AssertionError("不应执行影子任务")

    dispatcher = ShadowDispatcher(
        handler=handler,
        enabled=False,
        queue_size=1,
        worker_count=1,
        shutdown_timeout=0.1,
    )

    await dispatcher.start()

    assert dispatcher.is_running is False
    assert dispatcher.submit(create_task()) is False


@pytest.mark.asyncio
async def test_dispatcher_processes_submitted_task() -> None:
    """测试后台 Worker 消费影子预测任务"""
    processed: list[ShadowTask] = []
    completed = asyncio.Event()

    async def handler(shadow_task: ShadowTask) -> None:
        processed.append(shadow_task)
        completed.set()

    dispatcher = ShadowDispatcher(
        handler=handler,
        enabled=True,
        queue_size=2,
        worker_count=1,
        shutdown_timeout=1.0,
    )
    task = create_task()

    await dispatcher.start()
    assert dispatcher.submit(task) is True
    await asyncio.wait_for(
        completed.wait(),
        timeout=1.0,
    )
    await dispatcher.stop()

    assert processed == [task]
    assert dispatcher.is_running is False


@pytest.mark.asyncio
async def test_dispatcher_rejects_task_when_queue_is_full() -> None:
    """测试影子预测队列满时拒绝新任务"""
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(_task: ShadowTask) -> None:
        started.set()
        await release.wait()

    dispatcher = ShadowDispatcher(
        handler=handler,
        enabled=True,
        queue_size=1,
        worker_count=1,
        shutdown_timeout=1.0,
    )

    await dispatcher.start()
    assert dispatcher.submit(create_task("req_1")) is True
    await asyncio.wait_for(
        started.wait(),
        timeout=1.0,
    )
    assert dispatcher.submit(create_task("req_2")) is True
    assert dispatcher.submit(create_task("req_3")) is False
    release.set()
    await dispatcher.stop()


@pytest.mark.asyncio
async def test_dispatcher_continues_after_handler_error() -> None:
    """测试单个影子任务失败后继续消费"""
    completed = asyncio.Event()

    async def handler(shadow_task: ShadowTask) -> None:
        if shadow_task.request_id == "req_failed":
            raise RuntimeError("shadow failed")

        completed.set()

    dispatcher = ShadowDispatcher(
        handler=handler,
        enabled=True,
        queue_size=2,
        worker_count=1,
        shutdown_timeout=1.0,
    )

    await dispatcher.start()
    assert dispatcher.submit(create_task("req_failed")) is True
    assert dispatcher.submit(create_task("req_success")) is True
    await asyncio.wait_for(
        completed.wait(),
        timeout=1.0,
    )
    await dispatcher.stop()
