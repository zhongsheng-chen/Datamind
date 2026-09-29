"""存储可观测性装饰器测试.

验证存储操作的成功日志、异常日志、上下文合并和函数元数据保留。

核心功能：
  - test_successful_method_returns_result_and_logs_debug:
    验证成功操作返回结果并记录调试日志
  - test_failing_method_logs_exception_and_reraises_same_error:
    验证失败操作记录异常并原样抛出
  - test_core_fields_override_same_named_context_fields:
    验证核心日志字段覆盖同名上下文
  - test_error_fields_override_same_named_context_fields:
    验证错误字段覆盖同名上下文
  - test_context_is_read_for_each_call:
    验证每次操作读取当前上下文
  - test_decorator_preserves_function_metadata:
    验证装饰器保留函数元数据
"""

from collections.abc import Iterator
from typing import Any

import pytest

from datamind.storage import observability
from datamind.storage.observability import observe_storage


class RecordingLogger:
    """记录结构化日志调用的测试日志器."""

    def __init__(self) -> None:
        self.debug_calls: list[
            tuple[str, dict[str, object]]
        ] = []
        self.exception_calls: list[
            tuple[str, dict[str, object]]
        ] = []

    def debug(
        self,
        event: str,
        **event_fields: object,
    ) -> None:
        """记录 debug 日志."""
        self.debug_calls.append(
            (
                event,
                event_fields,
            )
        )

    def exception(
        self,
        event: str,
        **event_fields: object,
    ) -> None:
        """记录 exception 日志."""
        self.exception_calls.append(
            (
                event,
                event_fields,
            )
        )


class DemoStorageBackend:
    """用于验证存储可观测性装饰器的测试对象."""

    @property
    def storage_type(
        self,
    ) -> str:
        """返回测试存储后端类型."""
        return self.__class__.__name__

    @observe_storage("put")
    def put_object(
        self,
        key: str,
        data: bytes,
    ) -> str:
        """保存测试对象."""
        assert data
        return key

    @observe_storage("get")
    def failing_get(
        self,
        key: str,
    ) -> bytes:
        """模拟读取对象失败."""
        raise RuntimeError(
            f"读取失败: {key}"
        )

    @observe_storage("calculate")
    def calculate(
        self,
        value: int,
    ) -> int:
        """执行测试计算."""
        return value * 2

    @observe_storage("metadata")
    def documented_operation(
        self,
        value: int,
    ) -> int:
        """用于验证函数元数据."""
        return value + 1


def install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    perf_values: list[float],
    context: dict[str, Any] | None = None,
) -> RecordingLogger:
    """安装确定性的上下文、计时器和日志器."""
    logger = RecordingLogger()
    value_iterator: Iterator[float] = iter(
        perf_values
    )
    context_data = (
        context.copy()
        if context is not None
        else {}
    )

    monkeypatch.setitem(
        vars(observability),
        "logger",
        logger,
    )
    monkeypatch.setitem(
        vars(observability),
        "get_context",
        lambda: context_data.copy(),
    )
    monkeypatch.setitem(
        vars(observability.time),
        "perf_counter",
        value_iterator.__next__,
    )

    return logger


def test_successful_method_returns_result_and_logs_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试方法成功执行后返回结果并记录 debug 日志."""
    logger = install_runtime(
        monkeypatch,
        perf_values=[
            10.0,
            10.125,
        ],
        context={
            "trace_id": "trace-001",
            "request_id": "request-001",
        },
    )
    backend = DemoStorageBackend()

    result = backend.put_object(
        "models/model.pkl",
        b"model data",
    )

    assert result == "models/model.pkl"
    assert logger.exception_calls == []
    assert logger.debug_calls == [
        (
            "存储操作成功",
            {
                "trace_id": "trace-001",
                "request_id": "request-001",
                "operation": "put",
                "status": "success",
                "latency_ms": 125.0,
                "storage_type": "DemoStorageBackend",
            },
        ),
    ]


def test_failing_method_logs_exception_and_reraises_same_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试方法失败后记录异常日志并重新抛出原异常."""
    logger = install_runtime(
        monkeypatch,
        perf_values=[
            20.0,
            20.04567,
        ],
        context={
            "source": "cli",
            "user": "admin",
        },
    )
    backend = DemoStorageBackend()

    with pytest.raises(
        RuntimeError,
        match="读取失败: models/missing.pkl",
    ) as exc_info:
        backend.failing_get(
            "models/missing.pkl"
        )

    assert isinstance(
        exc_info.value,
        RuntimeError,
    )
    assert logger.debug_calls == []
    assert logger.exception_calls == [
        (
            "存储操作失败",
            {
                "source": "cli",
                "user": "admin",
                "operation": "get",
                "status": "error",
                "latency_ms": 45.67,
                "storage_type": "DemoStorageBackend",
                "error_type": "RuntimeError",
                "error": (
                    "读取失败: models/missing.pkl"
                ),
            },
        ),
    ]


def test_core_fields_override_same_named_context_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试核心日志字段覆盖上下文中的同名字段."""
    logger = install_runtime(
        monkeypatch,
        perf_values=[
            1.0,
            1.01,
        ],
        context={
            "trace_id": "trace-001",
            "operation": "context-operation",
            "status": "context-status",
            "latency_ms": -1.0,
            "storage_type": "ContextStorage",
        },
    )
    backend = DemoStorageBackend()

    result = backend.calculate(4)

    assert result == 8
    assert logger.debug_calls == [
        (
            "存储操作成功",
            {
                "trace_id": "trace-001",
                "operation": "calculate",
                "status": "success",
                "latency_ms": 10.0,
                "storage_type": "DemoStorageBackend",
            },
        ),
    ]


def test_error_fields_override_same_named_context_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试异常字段覆盖上下文中的同名字段."""
    logger = install_runtime(
        monkeypatch,
        perf_values=[
            2.0,
            2.005,
        ],
        context={
            "error_type": "ContextError",
            "error": "context error",
        },
    )
    backend = DemoStorageBackend()

    with pytest.raises(RuntimeError):
        backend.failing_get(
            "models/missing.pkl"
        )

    event_name, event_fields = (
        logger.exception_calls[0]
    )

    assert event_name == "存储操作失败"
    assert event_fields["error_type"] == (
        "RuntimeError"
    )
    assert event_fields["error"] == (
        "读取失败: models/missing.pkl"
    )


def test_context_is_read_for_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试每次调用时重新读取当前上下文."""
    logger = RecordingLogger()
    contexts = iter(
        [
            {
                "trace_id": "trace-001",
            },
            {
                "trace_id": "trace-002",
            },
        ]
    )
    perf_values = iter(
        [
            1.0,
            1.001,
            2.0,
            2.002,
        ]
    )

    monkeypatch.setitem(
        vars(observability),
        "logger",
        logger,
    )
    monkeypatch.setitem(
        vars(observability),
        "get_context",
        contexts.__next__,
    )
    monkeypatch.setitem(
        vars(observability.time),
        "perf_counter",
        perf_values.__next__,
    )

    backend = DemoStorageBackend()

    first_result = backend.calculate(1)
    second_result = backend.calculate(2)

    assert first_result == 2
    assert second_result == 4
    assert logger.debug_calls == [
        (
            "存储操作成功",
            {
                "trace_id": "trace-001",
                "operation": "calculate",
                "status": "success",
                "latency_ms": 1.0,
                "storage_type": "DemoStorageBackend",
            },
        ),
        (
            "存储操作成功",
            {
                "trace_id": "trace-002",
                "operation": "calculate",
                "status": "success",
                "latency_ms": 2.0,
                "storage_type": "DemoStorageBackend",
            },
        ),
    ]


def test_decorator_preserves_function_metadata() -> None:
    """测试 functools.wraps 保留函数名称和文档."""
    method = DemoStorageBackend.documented_operation

    assert method.__name__ == (
        "documented_operation"
    )
    assert method.__doc__ == (
        "用于验证函数元数据."
    )
