"""运行时任务队列异常测试

验证任务发布和批次取消异常的继承关系与消息保留行为。

核心功能：
  - test_task_queue_errors_inherit_runtime_error:
    验证任务队列异常继承运行时异常
  - test_task_queue_errors_preserve_message:
    验证任务队列异常保留错误消息
"""

import pytest

from datamind.runtime.task_queue.errors import (
    BatchCancelledError,
    TaskDispatchError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        TaskDispatchError,
        BatchCancelledError,
    ],
)
def test_task_queue_errors_inherit_runtime_error(
        error_type: type[RuntimeError],
) -> None:
    """测试任务队列异常继承 RuntimeError"""
    assert issubclass(
        error_type,
        RuntimeError,
    )


@pytest.mark.parametrize(
    "error_type",
    [
        TaskDispatchError,
        BatchCancelledError,
    ],
)
def test_task_queue_errors_preserve_message(
        error_type: type[RuntimeError],
) -> None:
    """测试任务队列异常保留错误消息"""
    error = error_type(
        "task queue failure"
    )

    assert str(error) == "task queue failure"
    assert error.args == (
        "task queue failure",
    )
