# tests/test_logging.py

"""日志模块测试

测试日志系统的所有核心功能：
  - 日志上下文管理
  - 日志格式化器
  - 日志过滤器
  - 日志处理器
  - 日志管理器
  - 启动日志缓存
  - 日志清理
"""

import os
import json
import time
import logging
from datetime import datetime
import pytest

from datamind.config import (
    LoggingConfig, LogLevel, LogFormat, RotationStrategy,
    TimeZone, TimestampPrecision
)
from datamind.core.logging.manager import LogManager
from datamind.core.logging.context import (
    get_request_id, set_request_id, has_request_id, clear_request_id,
    get_trace_id, set_trace_id, has_trace_id, clear_trace_id,
    get_span_id, set_span_id, clear_span_id, has_span_id,
    get_parent_span_id, set_parent_span_id, clear_parent_span_id, has_parent_span_id,
    generate_request_id, generate_trace_id, generate_span_id,
    ensure_request, ensure_trace, ensure_span,
    RequestContext, SpanContext,
    get_context, set_context, reset_context,
    with_request_id, with_span,
)
from datamind.core.logging.debug import (
    debug_print, info_print, warning_print, error_print
)
from datamind.core.logging.bootstrap import (
    install_bootstrap_logger, flush_bootstrap_logs, set_debug_mode,
    bootstrap_info, get_bootstrap_logger, get_buffer_size
)
from datamind.core.logging.cleanup import CleanupManager
from datamind.core.logging.filters import (
    RequestIdFilter, SensitiveDataFilter, SamplingFilter
)
from datamind.core.logging.formatters import (
    TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
)
from datamind.core.logging.handlers import (
    TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
)


# ==================== Logging Fixtures ====================

@pytest.fixture(autouse=True)
def reset_logging_state():
    """每个测试前后完全重置日志系统状态"""
    _reset_logging_system()
    yield
    _reset_logging_system()


def _reset_logging_system():
    """重置整个日志系统到初始状态"""
    # 重置 LogManager 单例
    LogManager._instance = None
    if hasattr(LogManager, '_initialized'):
        LogManager._initialized = False

    # 重置 context 上下文
    reset_context()

    # 重置 bootstrap 状态
    try:
        from datamind.core.logging import bootstrap
        bootstrap._bootstrap_handler = None
        bootstrap._bootstrap_logger = None
        bootstrap._bootstrap_flushed = False
        bootstrap._bootstrap_initialized = False
        bootstrap._config = bootstrap.BootstrapConfig.from_env()
    except:
        pass

    # 清理所有日志处理器
    for name in list(logging.root.manager.loggerDict.keys()):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    # 清理 root logger
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)


@pytest.fixture
def temp_log_dir():
    """临时日志目录"""
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_log_dir):
    """测试日志配置"""
    config = LoggingConfig()
    config.log_dir = temp_log_dir
    config.name = "test_app"
    config.manager_debug = True
    config.context_debug = True
    config.mask_sensitive = False
    config.use_async = False
    config.console_output = False
    config.enable_access_log = True
    config.enable_audit_log = True
    config.enable_performance_log = True
    return config


@pytest.fixture
def test_log_manager(test_config):
    """测试日志管理器"""
    manager = LogManager()
    manager.initialize(test_config)
    yield manager
    manager.cleanup()


# ==================== 上下文管理测试 ====================

class TestContext:
    """测试上下文管理"""

    def test_request_id(self):
        """测试请求ID"""
        set_request_id("test-123")
        assert get_request_id() == "test-123"

        set_request_id("test-456")
        assert get_request_id() == "test-456"

        # 测试默认值
        reset_context()
        assert get_request_id() == "-"

    def test_trace_id(self):
        """测试链路ID"""
        set_trace_id("trace-123")
        assert get_trace_id() == "trace-123"

        reset_context()
        assert get_trace_id() == "-"

    def test_span_id(self):
        """测试调用层级ID"""
        set_span_id("span-123")
        assert get_span_id() == "span-123"

        reset_context()
        assert get_span_id() == "-"

    def test_parent_span_id(self):
        """测试父级Span ID"""
        # 初始状态
        assert get_parent_span_id() == "-"

        # 设置父级 span
        set_parent_span_id("parent-span-123")
        assert get_parent_span_id() == "parent-span-123"

        # 重置
        reset_context()
        assert get_parent_span_id() == "-"

    def test_has_request_id(self):
        """测试检查请求ID是否存在"""
        reset_context()
        assert has_request_id() is False

        set_request_id("test-123")
        assert has_request_id() is True

    def test_has_trace_id(self):
        """测试检查trace ID是否存在"""
        reset_context()
        assert has_trace_id() is False

        set_trace_id("trace-123")
        assert has_trace_id() is True

    def test_has_span_id(self):
        """测试检查span ID是否存在"""
        reset_context()
        assert has_span_id() is False

        set_span_id("span-123")
        assert has_span_id() is True

    def test_has_parent_span_id(self):
        """测试检查parent span ID是否存在"""
        reset_context()
        assert has_parent_span_id() is False

        set_parent_span_id("parent-123")
        assert has_parent_span_id() is True

    def test_clear_request_id(self):
        """测试清除请求ID"""
        set_request_id("test-123")
        assert get_request_id() == "test-123"

        clear_request_id()
        assert get_request_id() == "-"

    def test_clear_trace_id(self):
        """测试清除trace ID"""
        set_trace_id("trace-123")
        assert get_trace_id() == "trace-123"

        clear_trace_id()
        assert get_trace_id() == "-"

    def test_clear_span_id(self):
        """测试清除span ID"""
        set_span_id("span-123")
        assert get_span_id() == "span-123"

        clear_span_id()
        assert get_span_id() == "-"

    def test_clear_parent_span_id(self):
        """测试清除parent span ID"""
        set_parent_span_id("parent-123")
        assert get_parent_span_id() == "parent-123"

        clear_parent_span_id()
        assert get_parent_span_id() == "-"

    def test_ensure_request(self):
        """测试确保请求ID存在"""
        reset_context()
        assert get_request_id() == "-"

        ensure_request()
        assert get_request_id() != "-"
        assert get_request_id().startswith("req-")

        # 再次调用不应改变现有ID
        current_id = get_request_id()
        ensure_request()
        assert get_request_id() == current_id

    def test_ensure_trace(self):
        """测试确保trace存在"""
        reset_context()
        assert get_trace_id() == "-"

        ensure_trace()
        assert get_trace_id() != "-"
        assert get_trace_id().startswith("trace-")

        # 再次调用不应改变现有ID
        current_id = get_trace_id()
        ensure_trace()
        assert get_trace_id() == current_id

    def test_ensure_trace_with_request(self):
        """测试确保trace同时创建request"""
        reset_context()
        assert get_request_id() == "-"
        assert get_trace_id() == "-"

        ensure_trace(create_request=True)
        assert get_request_id() != "-"
        assert get_trace_id() != "-"

    def test_ensure_span(self):
        """测试确保span存在"""
        reset_context()
        assert get_span_id() == "-"

        ensure_span()
        assert get_span_id() != "-"
        assert get_span_id().startswith("span-")

        # 再次调用不应改变现有ID
        current_id = get_span_id()
        ensure_span()
        assert get_span_id() == current_id

    def test_ensure_span_with_parent(self):
        """测试确保span同时创建parent_span"""
        reset_context()
        assert get_span_id() == "-"
        assert get_parent_span_id() == "-"

        ensure_span(create_parent_span=True)
        assert get_span_id() != "-"
        assert get_parent_span_id() != "-"

    def test_span_context(self):
        """测试Span上下文管理器"""
        set_span_id("parent")
        assert get_parent_span_id() == "-"

        with SpanContext("test_span"):
            span_id = get_span_id()
            parent_id = get_parent_span_id()

            assert span_id != "parent"
            assert span_id.startswith("span-")
            assert parent_id == "parent"

        assert get_span_id() == "parent"
        assert get_parent_span_id() == "-"

    def test_nested_spans(self):
        """测试嵌套Span"""
        set_span_id("root")
        assert get_parent_span_id() == "-"

        with SpanContext("level1"):
            level1_id = get_span_id()
            assert get_parent_span_id() == "root"

            with SpanContext("level2"):
                level2_id = get_span_id()
                assert get_parent_span_id() == level1_id
                assert level2_id != level1_id

            assert get_span_id() == level1_id
            assert get_parent_span_id() == "root"

        assert get_span_id() == "root"
        assert get_parent_span_id() == "-"

    def test_request_context(self):
        """测试请求上下文管理器"""
        set_request_id("old")
        set_trace_id("old-trace")

        with RequestContext(request_id="new", trace_id="new-trace"):
            assert get_request_id() == "new"
            assert get_trace_id() == "new-trace"

        assert get_request_id() == "old"
        assert get_trace_id() == "old-trace"

    def test_generate_ids(self):
        """测试生成ID函数"""
        req_id = generate_request_id()
        assert req_id.startswith("req-")
        assert len(req_id) > 10

        trace_id = generate_trace_id()
        assert trace_id.startswith("trace-")
        assert len(trace_id) > 10

        span_id = generate_span_id()
        assert span_id.startswith("span-")
        assert len(span_id) > 5

    def test_get_context(self):
        """测试获取完整上下文"""
        set_request_id("req-123")
        set_trace_id("trace-456")
        set_span_id("span-789")

        ctx = get_context()
        assert ctx['request_id'] == "req-123"
        assert ctx['trace_id'] == "trace-456"
        assert ctx['span_id'] == "span-789"
        assert ctx['parent_span_id'] == "-"

    def test_set_context(self):
        """测试批量设置上下文"""
        set_context(
            request_id="req-123",
            trace_id="trace-456",
            span_id="span-789",
            parent_span_id="parent-111"
        )

        assert get_request_id() == "req-123"
        assert get_trace_id() == "trace-456"
        assert get_span_id() == "span-789"
        assert get_parent_span_id() == "parent-111"

    def test_reset_context(self):
        """测试重置上下文"""
        set_request_id("test-123")
        set_trace_id("test-456")
        set_span_id("test-789")

        reset_context()

        assert get_request_id() == "-"
        assert get_trace_id() == "-"
        assert get_span_id() == "-"
        assert get_parent_span_id() == "-"

    def test_with_request_id_decorator(self):
        """测试请求ID装饰器"""
        original_id = get_request_id()

        @with_request_id("decorator-123")
        def test_func():
            return get_request_id()

        result = test_func()
        assert result == "decorator-123"
        assert get_request_id() == original_id

    def test_with_span_decorator(self):
        """测试Span装饰器"""
        set_span_id("root")

        @with_span("test_span")
        def test_func():
            span_id = get_span_id()
            parent_id = get_parent_span_id()
            return span_id, parent_id

        span_id, parent_id = test_func()
        assert span_id.startswith("span-")
        assert parent_id == "root"
        assert get_span_id() == "root"


# ==================== 调试工具测试 ====================

class TestDebug:
    """测试调试工具"""

    def test_debug_print(self, capsys):
        """测试调试打印"""
        debug_print("TestComponent", "测试消息: %s", "value")
        captured = capsys.readouterr()
        assert "TestComponent" in captured.err
        assert "测试消息: value" in captured.err

    def test_info_print(self, capsys):
        """测试信息打印"""
        info_print("TestComponent", "信息消息")
        captured = capsys.readouterr()
        assert "[INFO]" in captured.err

    def test_error_print(self, capsys):
        """测试错误打印"""
        error_print("TestComponent", "错误消息")
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.err

    def test_warning_print(self, capsys):
        """测试警告打印"""
        warning_print("TestComponent", "警告消息")
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.err


# ==================== 启动日志测试 ====================

class TestBootstrap:
    """测试启动日志"""

    def test_install_bootstrap(self):
        """测试安装启动日志"""
        install_bootstrap_logger()
        logger = get_bootstrap_logger()
        assert logger is not None
        assert logger.name.endswith(".bootstrap")

    def test_bootstrap_logging(self):
        """测试启动日志记录"""
        install_bootstrap_logger()
        bootstrap_info("测试启动消息")
        assert get_buffer_size() > 0

    def test_flush_bootstrap(self, test_log_manager):
        """测试刷新启动日志"""
        install_bootstrap_logger()
        bootstrap_info("启动日志测试消息")
        assert get_buffer_size() == 1

        flush_bootstrap_logs()
        assert get_buffer_size() == 0


# ==================== 格式化器测试 ====================

class TestTimezoneFormatter:
    """测试时区格式化器"""

    def test_init(self, test_config):
        """测试初始化"""
        formatter = TimezoneFormatter(test_config)
        assert formatter is not None

    def test_format_time_utc(self, test_config):
        """测试UTC时间格式化"""
        test_config.timezone = TimeZone.UTC
        formatter = TimezoneFormatter(test_config)
        dt = datetime(2024, 1, 1, 12, 0, 0)
        formatted = formatter.format_time(dt)
        assert formatted.tzinfo is not None

    def test_format_timestamp(self, test_config):
        """测试时间戳格式化"""
        test_config.json_use_epoch = False
        formatter = TimezoneFormatter(test_config)
        result = formatter.format_timestamp()
        assert isinstance(result, str)

    def test_format_timestamp_epoch(self, test_config):
        """测试时间戳格式化为epoch"""
        test_config.json_use_epoch = True
        test_config.json_epoch_unit = 'seconds'
        formatter = TimezoneFormatter(test_config)
        result = formatter.format_timestamp()
        assert isinstance(result, (int, float))


class TestJsonFormatter:
    """测试JSON格式化器"""

    def test_init(self, test_config):
        """测试初始化"""
        formatter = CustomJsonFormatter(test_config)
        assert formatter is not None

    def test_format(self, test_config):
        """测试JSON格式化"""
        formatter = CustomJsonFormatter(test_config)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="测试消息", args=(), exc_info=None
        )
        record.request_id = "test-123"
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed['level'] == "INFO"
        assert parsed['message'] == "测试消息"


class TestTextFormatter:
    """测试文本格式化器"""

    def test_init(self, test_config):
        """测试初始化"""
        formatter = CustomTextFormatter(test_config)
        assert formatter is not None

    def test_format(self, test_config):
        """测试文本格式化"""
        formatter = CustomTextFormatter(test_config)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="测试消息", args=(), exc_info=None
        )
        result = formatter.format(record)
        assert "测试消息" in result


# ==================== 过滤器测试 ====================

class TestFilters:
    """测试过滤器"""

    def test_request_id_filter(self, test_config):
        """测试请求ID过滤器"""
        filter = RequestIdFilter()
        filter.set_config(test_config)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="测试", args=(), exc_info=None
        )
        set_request_id("test-request-123")
        assert filter.filter(record) is True
        assert record.request_id == "test-request-123"

    def test_sensitive_data_filter(self, test_config):
        """测试敏感数据过滤器"""
        test_config.mask_sensitive = True
        test_config.sensitive_fields = {"password", "token"}
        filter = SensitiveDataFilter(test_config)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg='{"password": "secret123", "token": "abc123"}',
            args=(), exc_info=None
        )
        filter.filter(record)
        assert "secret123" not in record.msg
        assert "abc123" not in record.msg

    def test_sampling_filter_rate(self, test_config):
        """测试采样过滤器 - 采样率"""
        test_config.sampling_rate = 0.5
        filter = SamplingFilter(test_config)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="测试", args=(), exc_info=None
        )
        results = [filter.filter(record) for _ in range(10)]
        assert True in results
        assert False in results

    def test_sampling_filter_error_always(self, test_config):
        """测试采样过滤器 - 错误级别总是记录"""
        test_config.sampling_rate = 0.0
        filter = SamplingFilter(test_config)
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="test.py",
            lineno=10, msg="测试", args=(), exc_info=None
        )
        assert filter.filter(record) is True


# ==================== 处理器测试 ====================

class TestHandlers:
    """测试处理器"""

    def test_time_rotating_handler(self, test_config, temp_log_dir):
        """测试时间轮转处理器"""
        log_file = os.path.join(temp_log_dir, "test.log")
        handler = TimeRotatingFileHandlerWithTimezone(
            filename=log_file, when='midnight', interval=1,
            backupCount=5, encoding='utf-8', config=test_config
        )
        assert handler is not None
        handler.close()

    def test_async_handler(self, test_config, temp_log_dir):
        """测试异步处理器"""
        log_file = os.path.join(temp_log_dir, "test.log")
        file_handler = logging.FileHandler(log_file)
        async_handler = AsyncLogHandler(test_config, file_handler)
        assert async_handler is not None
        async_handler.close()


# ==================== 日志管理器测试 ====================

class TestLogManager:
    """测试日志管理器"""

    def test_singleton(self):
        """测试单例模式"""
        manager1 = LogManager()
        manager2 = LogManager()
        assert manager1 is manager2

    def test_initialize(self, test_config):
        """测试初始化"""
        manager = LogManager()
        assert manager.initialize(test_config) is True
        assert manager._initialized is True
        manager.cleanup()

    def test_get_app_logger(self, test_log_manager):
        """测试获取应用日志器"""
        logger = test_log_manager.logger
        assert logger is not None
        assert logger.name == "test_app"

    def test_log_access(self, test_log_manager):
        """测试访问日志"""
        test_log_manager.log_access(
            method="GET", path="/api/test", status=200,
            duration_ms=100.5, ip="127.0.0.1"
        )
        assert test_log_manager.get_stats()['logs_processed'] > 0

    def test_log_audit(self, test_log_manager):
        """测试审计日志"""
        test_log_manager.log_audit(
            action="USER_LOGIN", user_id="user123", ip_address="127.0.0.1"
        )
        assert test_log_manager.get_stats()['logs_processed'] > 0

    def test_log_performance(self, test_log_manager):
        """测试性能日志"""
        test_log_manager.log_performance(
            operation="DB_QUERY", duration_ms=50.5,
            query="SELECT * FROM users", rows=10
        )
        assert test_log_manager.get_stats()['logs_processed'] > 0

    def test_set_request_id(self, test_log_manager):
        """测试设置请求ID"""
        test_log_manager.set_request_id("test-request-456")
        assert test_log_manager.get_request_id() == "test-request-456"

    def test_get_current_time(self, test_log_manager):
        """测试获取当前时间"""
        assert test_log_manager.get_current_time() is not None

    def test_get_stats(self, test_log_manager):
        """测试获取统计信息"""
        stats = test_log_manager.get_stats()
        assert 'logs_processed' in stats
        assert 'errors' in stats
        assert 'warnings' in stats


# ==================== 日志清理测试 ====================

class TestCleanup:
    """测试日志清理"""

    def test_collect_log_files(self, test_config):
        """测试收集日志文件"""
        test_config.file = "app.log"
        test_config.error_file = "error.log"
        test_config.access_log_file = "access.log"
        test_config.text_suffix = "text"
        test_config.json_suffix = "json"

        formatter = TimezoneFormatter(test_config)
        cleanup_mgr = CleanupManager(test_config, formatter)
        files = cleanup_mgr._collect_log_files()
        assert len(files) > 0

    def test_get_both_filename(self, test_config):
        """测试获取BOTH格式文件名"""
        test_config.format = LogFormat.BOTH
        test_config.text_suffix = "text"
        test_config.json_suffix = "json"

        formatter = TimezoneFormatter(test_config)
        cleanup_mgr = CleanupManager(test_config, formatter)
        text_file = cleanup_mgr._get_both_filename("app.log", "text")
        assert "text" in text_file


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""

    def test_full_logging_flow(self, temp_log_dir):
        """测试完整日志流程"""
        config = LoggingConfig()
        config.log_dir = temp_log_dir
        config.file = "app.log"
        config.name = "test_app"
        config.enable_access_log = True
        config.enable_audit_log = True
        config.enable_performance_log = True

        manager = LogManager()
        manager.initialize(config)
        manager.set_request_id("integration-test-123")

        manager.log_access(method="POST", path="/api/test", status=201)
        manager.log_audit(action="TEST_ACTION", user_id="tester")
        manager.log_performance(operation="TEST_OP", duration_ms=10.5)

        stats = manager.get_stats()
        assert stats['logs_processed'] >= 3
        manager.cleanup()

    def test_bootstrap_and_flush(self, temp_log_dir):
        """测试启动日志缓存和刷新"""
        import datamind.core.logging.bootstrap as bootstrap_module

        # 重置所有状态
        _reset_logging_system()

        # 清除环境变量
        env_vars = ['DATAMIND_LOG_DIR', 'DATAMIND_LOG_NAME', 'DATAMIND_LOG_FORMAT',
                    'DATAMIND_LOG_FILE', 'DATAMIND_ERROR_LOG_FILE', 'DATAMIND_APP_NAME']
        old_env = {var: os.environ.pop(var, None) for var in env_vars}

        try:
            # 安装并记录启动日志
            set_debug_mode(True)
            install_bootstrap_logger()
            bootstrap_info("启动测试消息1")
            bootstrap_info("启动测试消息2")

            # 验证缓存
            assert get_buffer_size() == 2, f"预期2条日志，实际{get_buffer_size()}"

            # 创建配置
            config = LoggingConfig()
            config.log_dir = temp_log_dir
            config.file = "app.log"
            config.name = "test_app"
            config.format = LogFormat.TEXT
            config.use_async = False
            config.console_output = False

            # 初始化并验证
            manager = LogManager()
            manager.initialize(config)
            time.sleep(0.5)

            expected_file = os.path.join(temp_log_dir, "app.log")
            assert os.path.exists(expected_file), f"日志文件不存在: {expected_file}"

            with open(expected_file) as f:
                content = f.read()
                assert "启动测试消息1" in content
                assert "启动测试消息2" in content

            manager.cleanup()

        finally:
            for var, value in old_env.items():
                if value is not None:
                    os.environ[var] = value


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""

    def test_async_logging_performance(self, temp_log_dir):
        """测试异步日志性能"""
        config = LoggingConfig()
        config.log_dir = temp_log_dir
        config.file = "app.log"
        config.use_async = True

        manager = LogManager()
        manager.initialize(config)

        start_time = time.time()
        for i in range(100):
            manager.log_access(method="GET", path=f"/api/test/{i}", status=200)
        duration = time.time() - start_time

        assert duration < 1.0
        manager.cleanup()


# ==================== 异常测试 ====================

class TestExceptions:
    """异常测试"""

    def test_invalid_config(self):
        """测试无效配置 - 空 log_dir"""
        os.environ.pop('DATAMIND_LOG_DIR', None)

        config = LoggingConfig()
        config.log_dir = ""

        manager = LogManager()
        with pytest.raises(ValueError, match="log_dir 不能为空"):
            manager.initialize(config)