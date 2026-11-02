"""第三方诊断完整性、接入幂等性、警告语义与进程归属测试."""

import io
import json
import logging
import os
import subprocess
import sys
import warnings

import pytest
import structlog

from datamind.config.logging import LoggingConfig
from datamind.logging.setup import setup_logging, shutdown_logging


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
def reset_foreign_logging():
    """只恢复接入拥有的配置，避免影响其他测试的警告捕获."""
    original_config = structlog.get_config().copy()
    shutdown_logging()
    try:
        yield
    finally:
        shutdown_logging()
        structlog.configure(**original_config)


def configure(tmp_path, fmt="json", **kwargs):
    """创建输出到临时文件的实际 formatter/handler 链路."""
    config = LoggingConfig(
        _env_file=None,
        level="DEBUG",
        format=fmt,
        dir=tmp_path,
        filename="foreign.log",
        enable_console=False,
        enable_file=True,
        enable_async=kwargs.pop("enable_async", False),
        sample_rate=kwargs.pop("sample_rate", 1.0),
    )
    setup_logging(config, **kwargs)
    return tmp_path / "foreign.log"


def finish(path):
    """等待异步队列排空后读取最终输出."""
    shutdown_logging()
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("fmt", ["text", "json"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_foreign_multiline_and_record_are_preserved(tmp_path, fmt, asynchronous):
    """多行内容完整，字段位于文本第一行，JSON 保留换行和原始级别."""
    path = configure(tmp_path, fmt, enable_async=asynchronous, worker_id="actual-worker", service_id="actual-service")
    logger = logging.getLogger("__cvxpy__")
    original_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        record = logger.makeRecord(
            logger.name, logging.WARNING, "/original/solver.py", 42, "%s", (MESSAGE,), None, extra={"api_key": "secret-value"}
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
def test_exception_and_stack_survive_queue_and_formatter(tmp_path, fmt):
    """已有 exc_info 和 stack_info 均完整保留，不把 WARNING 改成 ERROR."""
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


def test_delayed_cvxpy_handler_and_reinitialization_do_not_duplicate(tmp_path):
    """延迟导入追加的 handler 和重复 setup 不增加输出副本."""
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
    assert [json.loads(line)["event"] for line in output.splitlines()] == ["first event", "second event"]
    assert logger.propagate == original_propagate
    assert logger.handlers == original_handlers + [default_handler]
    logger.removeHandler(default_handler)
    default_handler.close()


def test_no_new_sampling_or_cross_worker_deduplication(tmp_path, monkeypatch):
    """应用采样会丢弃普通日志时，仍保留各 Worker 实际发出的第三方诊断."""
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


def test_warning_original_message_source_and_filters(tmp_path):
    """保留标准 formatwarning 的类别、完整文本、路径、行号和源码行."""
    original_filters = warnings.filters.copy()
    original_showwarning = warnings.showwarning
    source = tmp_path / "sklearn_base.py"
    source.write_text('warnings.warn(\n    "warning details",\n)\n', encoding="utf-8")
    path = configure(tmp_path)
    assert warnings.filters == original_filters
    with warnings.catch_warnings():
        warnings.simplefilter("default", UserWarning)
        registry = {}
        for _ in range(2):
            warnings.warn_explicit(WARNING, UserWarning, str(source), 1, registry=registry)
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


def test_existing_warning_capture_is_not_disabled(tmp_path):
    """外部调用者拥有的 captureWarnings 在应用清理后仍有效."""
    logging.captureWarnings(True)
    captured = warnings.showwarning
    try:
        configure(tmp_path)
        shutdown_logging()
        assert warnings.showwarning is captured
    finally:
        logging.captureWarnings(False)


def test_inherited_parent_worker_identity_is_not_fabricated(tmp_path):
    """尚未重新初始化的 fork 子进程记录不沿用父 Worker 标识."""
    path = configure(tmp_path, worker_id="parent-worker")
    logger = logging.getLogger("__cvxpy__")
    record = logger.makeRecord(logger.name, logging.WARNING, __file__, 1, MESSAGE, (), None)
    record.process = os.getpid() + 100000
    logger.handle(record)
    event = json.loads(finish(path))
    assert event["pid"] == record.process
    assert "worker_id" not in event


def test_native_stderr_remains_visible(tmp_path, capsys):
    """不接管原生库 stderr；不可靠接入的输出原样保留."""
    configure(tmp_path)
    print("native library diagnostic", file=sys.stderr)
    assert capsys.readouterr().err == "native library diagnostic\n"


def test_child_process_initializes_its_own_logging(tmp_path):
    """全新进程使用真实 pid，并保持原始 logger 名称和多行消息."""
    code = """
import logging, os
from datamind.config.logging import LoggingConfig
from datamind.logging import setup_logging, shutdown_logging
config = LoggingConfig(_env_file=None, level="INFO", format="json", enable_file=False, enable_console=True, console_level="WARNING")
setup_logging(config, worker_id=f"child-{os.getpid()}")
logging.getLogger("__cvxpy__").warning("original first line\\noriginal detail")
shutdown_logging()
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    event = json.loads(result.stdout)
    assert event["worker_id"] == f"child-{event['pid']}"
    assert event["pid"] != os.getpid()
    assert event["event"] == "original first line\noriginal detail"
    assert event["logger"] == "__cvxpy__"
    assert result.stderr == ""


def test_silent_application_does_not_swallow_unmanaged_warning():
    """没有可用输出通道时，不替换第三方已有输出方式."""
    previous = warnings.showwarning
    handlers = logging.getLogger("__cvxpy__").handlers.copy()
    config = LoggingConfig(_env_file=None, enable_file=False, enable_console=False)
    setup_logging(config)
    assert warnings.showwarning is previous
    assert logging.getLogger("__cvxpy__").handlers == handlers


def test_original_log_record_custom_level_is_preserved(tmp_path):
    """不根据 Exception 字样重分类原始日志级别."""
    path = configure(tmp_path)
    logger = logging.getLogger("__cvxpy__")
    record = logger.makeRecord(
        logger.name, logging.INFO, "/original/file.py", 525, "Exception is diagnostic text: %s", ("original",), None
    )
    logger.handle(record)
    event = json.loads(finish(path))
    assert event["level"] == "info"
    assert event["event"] == "Exception is diagnostic text: original"


def test_warning_does_not_disappear_at_root_error_level(tmp_path):
    """接入 warnings 不引入原本不存在的 root 级别过滤."""
    root = logging.getLogger()
    warning_logger = logging.getLogger("py.warnings")
    previous_root_level, previous_warning_level = root.level, warning_logger.level
    root.setLevel(logging.ERROR)
    warning_logger.setLevel(logging.NOTSET)
    try:
        path = configure(tmp_path)
        with warnings.catch_warnings():
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
