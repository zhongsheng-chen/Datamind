"""第三方日志接入测试.

验证第三方日志与警告内容保留、重复接入和进程来源识别。

核心功能：
  - test_foreign_multiline_and_record_are_preserved:
    验证第三方多行日志保留完整内容、首行字段、换行和原始级别
  - test_exception_and_stack_survive_queue_and_formatter:
    验证日志经过队列和格式化后保留异常、堆栈及 WARNING 级别
  - test_delayed_cvxpy_handler_and_reinitialization_do_not_duplicate:
    验证延迟导入追加处理器和重复初始化均不增加日志副本
  - test_no_new_sampling_or_cross_worker_deduplication:
    验证应用启用采样时仍保留各 Worker 发出的第三方诊断
  - test_warning_original_message_source_and_filters:
    验证警告保留原始类别、完整文本、路径、行号和源码行
  - test_existing_warning_capture_is_not_disabled:
    验证应用清理后外部调用者启用的警告捕获仍然有效
  - test_inherited_parent_worker_identity_is_not_fabricated:
    验证未重新初始化的 fork 子进程不沿用父 Worker 标识
  - test_native_stderr_remains_visible:
    验证原生库标准错误输出保持可见且内容不变
  - test_child_process_initializes_its_own_logging:
    验证新进程使用真实进程 ID，并保留原始日志名称和多行消息
  - test_silent_application_does_not_swallow_unmanaged_warning:
    验证没有可用输出通道时保留第三方已有的警告输出方式
  - test_original_log_record_custom_level_is_preserved:
    验证日志中的 Exception 字样不会改变原始日志级别
  - test_warning_does_not_disappear_at_root_error_level:
    验证接入警告后不会额外应用 root 日志级别过滤
"""

import io
import json
import logging
import os
import subprocess
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog

from datamind.config.logging import LoggingConfig
from datamind.logging.setup import (
    setup_logging,
    shutdown_logging,
)


MESSAGE = (
    "Encountered unexpected exception importing solver HIGHS:\n"
    "ImportError('/usr/local/lib/python3.12/site-packages/highspy/_core.so: "
    "undefined symbol: _ZN5Highs13releaseMemoryEv')"
)
WARNING = (
    "Trying to unpickle estimator LogisticRegression from version 1.9.0 when using version 1.9.1.\n"
    "https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations"
)


@pytest.fixture(autouse=True)
def reset_foreign_logging() -> Iterator[None]:
    """只恢复接入拥有的配置，避免影响其他测试的警告捕获."""
    original_config = structlog.get_config().copy()
    shutdown_logging()

    try:
        yield
    finally:
        shutdown_logging()
        structlog.configure(**original_config)


def configure(
        tmp_path: Path,
        fmt: str = "json",
        *,
        enable_async: bool = False,
        sample_rate: float = 1.0,
        worker_id: str | None = None,
        service_id: str | None = None,
) -> Path:
    """创建输出到临时文件的实际 formatter/handler 链路."""
    config_values: dict[str, Any] = {
        "_env_file": None,
        "level": "DEBUG",
        "format": fmt,
        "dir": tmp_path,
        "filename": "foreign.log",
        "enable_console": False,
        "enable_file": True,
        "enable_async": enable_async,
        "sample_rate": sample_rate,
    }
    config = LoggingConfig(**config_values)
    setup_logging(
        config,
        worker_id=worker_id,
        service_id=service_id,
    )

    return tmp_path / "foreign.log"


def finish(
        path: Path,
) -> str:
    """等待异步队列排空后读取最终输出."""
    shutdown_logging()

    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("fmt", ["text", "json"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_foreign_multiline_and_record_are_preserved(
        tmp_path: Path,
        fmt: str,
        asynchronous: bool,
) -> None:
    """测试第三方多行日志保留完整内容、首行字段、换行和原始级别."""
    path = configure(
        tmp_path,
        fmt,
        enable_async=asynchronous,
        worker_id="actual-worker",
        service_id="actual-service",
    )
    logger = logging.getLogger("__cvxpy__")
    original_level = logger.level
    logger.setLevel(logging.INFO)

    try:
        record = logger.makeRecord(
            logger.name,
            logging.WARNING,
            "/original/solver.py",
            42,
            "%s",
            (MESSAGE,),
            None,
            extra={"api_key": "secret-value"},
        )
        before = record.__dict__.copy()
        logger.handle(record)
        output = finish(path)

        assert record.__dict__ == before

        if fmt == "json":
            event = json.loads(output)
            assert event["event"] == MESSAGE
            assert event["level"] == "warning"
            assert event["logger"] == "__cvxpy__"
            assert event["pid"] == os.getpid()
            assert event["worker_id"] == "actual-worker"
            assert event["service_id"] == "actual-service"
            assert "secret-value" not in output
        else:
            first, continuation = output.split("\n", 1)
            assert MESSAGE.split("\n")[0] in first
            assert "logger=__cvxpy__" in first
            assert "pid=" in first and "worker_id=actual-worker" in first
            assert continuation.rstrip("\n") == MESSAGE.split("\n", 1)[1]

        assert output.count("undefined symbol") == 1
    finally:
        logger.setLevel(original_level)


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_exception_and_stack_survive_queue_and_formatter(
        tmp_path: Path,
        fmt: str,
) -> None:
    """测试日志经过队列和格式化后保留异常、堆栈及 WARNING 级别."""
    path = configure(tmp_path, fmt, enable_async=True)
    logger = logging.getLogger("__cvxpy__")

    try:
        raise ImportError("/full/path.so: undefined symbol: _ZN5Highs13releaseMemoryEv")
    except ImportError:
        logger.warning(MESSAGE, exc_info=True, stack_info=True)

    output = finish(path)

    if fmt == "json":
        event = json.loads(output)
        assert event["event"] == MESSAGE
        assert event["level"] == "warning"
        assert "Traceback (most recent call last):" in event["exception"]
        assert "Stack (most recent call last):" in event["stack"]
    else:
        assert "| WARNING" in output.splitlines()[0]
        assert "Traceback (most recent call last):" in output
        assert "Stack (most recent call last):" in output

    assert "/full/path.so: undefined symbol: _ZN5Highs13releaseMemoryEv" in output


def test_delayed_cvxpy_handler_and_reinitialization_do_not_duplicate(
        tmp_path: Path,
) -> None:
    """测试延迟导入追加处理器和重复初始化均不增加日志副本."""
    logger = logging.getLogger("__cvxpy__")
    original_handlers = logger.handlers.copy()
    original_propagate = logger.propagate
    path = configure(tmp_path)
    raw = io.StringIO()
    default_handler = logging.StreamHandler(raw)
    logger.addHandler(default_handler)  # CVXPY settings 在导入时执行此操作。
    logger.propagate = False
    logger.warning("first event")
    configure(tmp_path)
    logger.warning("second event")
    output = finish(path)

    assert raw.getvalue() == ""
    assert [json.loads(line)["event"] for line in output.splitlines()] == [
        "first event",
        "second event",
    ]
    assert logger.propagate == original_propagate
    assert logger.handlers == original_handlers + [default_handler]

    logger.removeHandler(default_handler)
    default_handler.close()


def test_no_new_sampling_or_cross_worker_deduplication(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应用启用采样时仍保留各 Worker 发出的第三方诊断."""
    monkeypatch.setattr("datamind.logging.processors.random.random", lambda: 1.0)
    logger = logging.getLogger("__cvxpy__")
    level = logger.level
    logger.setLevel(logging.INFO)

    try:
        path = configure(tmp_path, sample_rate=0.01, worker_id="worker-a")
        logger.info(MESSAGE)
        configure(tmp_path, sample_rate=0.01, worker_id="worker-b")
        logger.warning(MESSAGE)
        events = [json.loads(line) for line in finish(path).splitlines()]
        assert [event["worker_id"] for event in events] == ["worker-a", "worker-b"]
        assert [event["level"] for event in events] == ["info", "warning"]
    finally:
        logger.setLevel(level)


def test_warning_original_message_source_and_filters(
        tmp_path: Path,
) -> None:
    """测试警告保留原始类别、完整文本、路径、行号和源码行."""
    original_filters = list(warnings.filters)
    original_showwarning = warnings.showwarning
    source = tmp_path / "sklearn_base.py"
    source.write_text('warnings.warn(\n    "warning details",\n)\n', encoding="utf-8")
    path = configure(tmp_path)

    assert warnings.filters == original_filters

    with warnings.catch_warnings(record=False):
        warnings.simplefilter("default", UserWarning)
        registry = {}

        for _ in range(2):
            warnings.warn_explicit(
                WARNING,
                UserWarning,
                str(source),
                1,
                registry=registry,
            )

        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.warn("ignored by existing filter", RuntimeWarning)

        warnings.simplefilter("error", DeprecationWarning)

        with pytest.raises(DeprecationWarning, match="still raises"):
            warnings.warn("still raises", DeprecationWarning)

    event = json.loads(finish(path))

    assert event["logger"] == "py.warnings"
    assert event["level"] == "warning"
    assert event["event"] == warnings.formatwarning(WARNING, UserWarning, str(source), 1)
    assert "warnings.warn(" in event["event"]
    assert warnings.showwarning is original_showwarning
    assert warnings.filters == original_filters


def test_existing_warning_capture_is_not_disabled(
        tmp_path: Path,
) -> None:
    """测试应用清理后外部调用者启用的警告捕获仍然有效."""
    logging.captureWarnings(True)
    captured = warnings.showwarning

    try:
        configure(tmp_path)
        shutdown_logging()
        assert warnings.showwarning is captured
    finally:
        logging.captureWarnings(False)


def test_inherited_parent_worker_identity_is_not_fabricated(
        tmp_path: Path,
) -> None:
    """测试未重新初始化的 fork 子进程不沿用父 Worker 标识."""
    path = configure(tmp_path, worker_id="parent-worker")
    logger = logging.getLogger("__cvxpy__")
    record = logger.makeRecord(
        logger.name,
        logging.WARNING,
        __file__,
        1,
        MESSAGE,
        (),
        None,
    )
    record.process = os.getpid() + 100000
    logger.handle(record)
    event = json.loads(finish(path))

    assert event["pid"] == record.process
    assert "worker_id" not in event


def test_native_stderr_remains_visible(
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
) -> None:
    """测试原生库标准错误输出保持可见且内容不变."""
    configure(tmp_path)
    print("native library diagnostic", file=sys.stderr)

    assert capsys.readouterr().err == "native library diagnostic\n"


def test_child_process_initializes_its_own_logging(
        tmp_path: Path,
) -> None:
    """测试新进程使用真实进程 ID，并保留原始日志名称和多行消息."""
    code = """
import logging
import os

from datamind.config.logging import LoggingConfig
from datamind.logging import setup_logging, shutdown_logging

config_values = {
    "_env_file": None,
    "level": "INFO",
    "format": "json",
    "enable_file": False,
    "enable_console": True,
    "console_level": "WARNING",
}
config = LoggingConfig(**config_values)
setup_logging(config, worker_id=f"child-{os.getpid()}")
logging.getLogger("__cvxpy__").warning("original first line\\noriginal detail")
shutdown_logging()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    event = json.loads(result.stdout)
    assert event["worker_id"] == f"child-{event['pid']}"
    assert event["pid"] != os.getpid()
    assert event["event"] == "original first line\noriginal detail"
    assert event["logger"] == "__cvxpy__"
    assert result.stderr == ""


def test_silent_application_does_not_swallow_unmanaged_warning() -> None:
    """测试没有可用输出通道时保留第三方已有的警告输出方式."""
    previous = warnings.showwarning
    handlers = logging.getLogger("__cvxpy__").handlers.copy()
    config_values: dict[str, Any] = {
        "_env_file": None,
        "enable_file": False,
        "enable_console": False,
    }
    config = LoggingConfig(**config_values)
    setup_logging(config)

    assert warnings.showwarning is previous
    assert logging.getLogger("__cvxpy__").handlers == handlers


def test_original_log_record_custom_level_is_preserved(
        tmp_path: Path,
) -> None:
    """测试日志中的 Exception 字样不会改变原始日志级别."""
    path = configure(tmp_path)
    logger = logging.getLogger("__cvxpy__")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "/original/file.py",
        525,
        "Exception is diagnostic text: %s",
        ("original",),
        None,
    )
    logger.handle(record)
    event = json.loads(finish(path))

    assert event["level"] == "info"
    assert event["event"] == "Exception is diagnostic text: original"


def test_warning_does_not_disappear_at_root_error_level(
        tmp_path: Path,
) -> None:
    """测试接入警告后不会额外应用 root 日志级别过滤."""
    root = logging.getLogger()
    warning_logger = logging.getLogger("py.warnings")
    previous_root_level, previous_warning_level = root.level, warning_logger.level
    root.setLevel(logging.ERROR)
    warning_logger.setLevel(logging.NOTSET)

    try:
        path = configure(tmp_path)

        with warnings.catch_warnings(record=False):
            warnings.simplefilter("always", UserWarning)
            warnings.warn("visible warning despite root ERROR", UserWarning)

        event = json.loads(finish(path))

        assert event["level"] == "warning"
        assert "visible warning despite root ERROR" in event["event"]
        assert root.level == logging.ERROR
        assert warning_logger.level == logging.NOTSET
    finally:
        shutdown_logging()
        root.setLevel(previous_root_level)
        warning_logger.setLevel(previous_warning_level)
