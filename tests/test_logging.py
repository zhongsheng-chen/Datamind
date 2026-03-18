# tests/test_logging.py

import os
import unittest
import logging
import json
import time
import tempfile
import shutil
import threading
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from datamind.core.logging import log_manager,get_request_id,set_request_id


class TestLogManager(unittest.TestCase):
    """测试日志管理器"""

    # 调试开关：控制是否打印信息，默认为 False（不打印调试）
    PRINT_DEBUG = os.getenv("LOGGING_TEST_DEBUG", "false").lower() == "true"

    @classmethod
    def setUpClass(cls):
        """测试类初始化并创建临时目录"""
        from datamind.core.logging.bootstrap import install_bootstrap_logger
        cls.test_dir = tempfile.mkdtemp(prefix="log_test_")
        cls.log_dir = Path(cls.test_dir) / "logs"
        cls.log_dir.mkdir(exist_ok=True)

        # 设置环境变量
        os.environ["DATAMIND_APP_NAME"] = "testapp"
        os.environ["DATAMIND_BOOTSTRAP_DEBUG"] = "false"

        # 安装 bootstrap 日志器
        install_bootstrap_logger()

    def setUp(self):
        """每个测试前的准备工作"""
        # 重置 log_manager 状态
        if hasattr(log_manager, '_initialized') and log_manager._initialized:
            log_manager.cleanup()
        log_manager._initialized = False
        log_manager._app_name = "testapp"

        # 确保没有遗留的处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 完全重置 bootstrap 状态
        from datamind.core.logging.bootstrap import (
            _bootstrap_handler,
            _bootstrap_logger,
            install_bootstrap_logger
        )

        # 清理旧的 bootstrap 资源
        if _bootstrap_logger and _bootstrap_handler:
            try:
                _bootstrap_logger.removeHandler(_bootstrap_handler)
                _bootstrap_handler.close()
            except:
                pass

        # 重置全局变量
        import datamind.core.logging.bootstrap as bootstrap_module
        bootstrap_module._bootstrap_handler = None
        bootstrap_module._bootstrap_logger = None
        bootstrap_module._bootstrap_flushed = False

        # 重新安装 bootstrap logger
        install_bootstrap_logger()

        # 确保环境变量正确
        os.environ["DATAMIND_APP_NAME"] = "testapp"
        os.environ["DATAMIND_LOG_NAME"] = "testapp"

        time.sleep(0.1)

    def tearDown(self):
        """每个测试后的清理工作"""
        if hasattr(log_manager, '_initialized') and log_manager._initialized:
            log_manager.cleanup()

        # 清理当前测试的日志文件
        for f in self.log_dir.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                except:
                    pass

    @classmethod
    def tearDownClass(cls):
        """测试类完成后的清理"""
        try:
            shutil.rmtree(cls.test_dir)
        except:
            pass

    def _debug_print(self, *args, **kwargs):
        """根据 PRINT_DEBUG 设置决定是否打印"""
        if self.PRINT_DEBUG:
            print(*args, **kwargs)

    def _get_config_digest(self, config) -> str:
        """获取配置摘要"""
        exclude = {'_env', '_base_dir', '_last_modified'}
        config_dict = config.model_dump(exclude=exclude)
        config_str = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _is_config_equivalent(self, config1, config2) -> bool:
        """判断两个配置是否等效"""
        return self._get_config_digest(config1) == self._get_config_digest(config2)

    def _create_base_config(self, **kwargs):
        """创建基础测试配置，支持 kwargs 覆盖"""
        from datamind.config import LoggingConfig, LogLevel, LogFormat, TimeZone, RotationStrategy

        # 创建基础配置
        base_config = LoggingConfig(
            # 基本配置
            name="testapp",
            level=LogLevel.DEBUG,
            encoding="utf-8",

            # 时间格式配置
            timezone=TimeZone.UTC,
            timestamp_precision="milliseconds",

            # 文本日志时间格式
            text_date_format="%Y-%m-%d %H:%M:%S",
            text_datetime_format="%Y-%m-%d %H:%M:%S.%f",

            # JSON日志时间格式
            json_timestamp_field="@timestamp",
            json_datetime_format="yyyy-MM-dd'T'HH:mm:ss.SSSZ",
            json_use_epoch=False,
            json_epoch_unit="milliseconds",

            # 日志文件名时间格式
            file_name_timestamp=False,
            file_name_date_format="%Y%m%d",

            # 日志目录配置
            log_dir=str(self.log_dir),

            # 文件配置 - 统一使用 testapp 前缀
            file="testapp.log",
            error_file="testapp.error.log",

            # 日志格式
            format=LogFormat.JSON,
            text_format="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(filename)s:%(lineno)d - %(message)s",
            json_format={
                "@timestamp": "asctime",
                "log.level": "levelname",
                "log.logger": "name",
                "message": "message",
                "trace.id": "extra.request_id",
                "source.file": "filename",
                "source.line": "lineno",
                "process.pid": "process",
            },

            # 文件轮转配置
            max_bytes=1024 * 1024,
            backup_count=2,

            # 时间轮转配置
            rotation_strategy=RotationStrategy.SIZE,
            rotation_when=None,
            rotation_interval=1,
            rotation_at_time=None,
            rotation_utc=False,

            # 旧日志清理
            retention_days=90,
            cleanup_at_time="03:00",

            # 并发处理
            use_concurrent=False,
            concurrent_lock_dir=str(self.log_dir / "locks"),

            # 异步日志
            use_async=False,
            async_queue_size=10000,

            # 日志采样
            sampling_rate=1.0,

            # 敏感信息脱敏
            mask_sensitive=True,
            sensitive_fields={"password", "token", "credit_card"},
            mask_char="*",

            # 日志分类
            enable_access_log=True,
            access_log_file="testapp.access.log",
            enable_audit_log=True,
            audit_log_file="testapp.audit.log",
            enable_performance_log=True,
            performance_log_file="testapp.performance.log",

            # 日志过滤
            filters={
                "exclude_paths": ["/health", "/metrics"],
                "exclude_status_codes": [404],
                "min_duration_ms": 0
            },

            # 远程日志
            enable_remote=False,
            remote_url=None,
            remote_token=None,
            remote_timeout=5,
            remote_batch_size=100,

            # 控制台输出
            console_output=False,
            console_level=LogLevel.INFO,

            # 归档配置
            archive_enabled=False,
            archive_path="archive",
            archive_compression="gz",

            # 调试配置
            formatter_debug=False,
            handler_debug=False,
            manager_debug=False,
            filter_debug=False,
            context_debug=False,
            cleanup_debug=False,
        )

        # 用 kwargs 覆盖
        final_config = base_config.model_copy(update=kwargs)

        # 打印调试信息（受 PRINT_DEBUG 控制）
        if kwargs and self.PRINT_DEBUG:
            self._debug_print(f"[TEST DEBUG] 配置覆盖: {kwargs}")

        return final_config

    def _initialize_with_config(self, **kwargs):
        """使用指定配置初始化日志管理器"""
        # 在测试中启用调试输出
        kwargs.setdefault('formatter_debug', False)
        kwargs.setdefault('handler_debug', False)
        kwargs.setdefault('manager_debug', False)
        kwargs.setdefault('filter_debug', False)
        kwargs.setdefault('context_debug', False)
        kwargs.setdefault('cleanup_debug', False)

        # 创建新配置
        self.config = self._create_base_config(**kwargs)

        # 确保 log_dir 是绝对路径
        if not os.path.isabs(self.config.log_dir):
            self.config.log_dir = str(Path(self.test_dir) / self.config.log_dir)

        # 确保完全重置 log_manager
        if hasattr(log_manager, '_initialized') and log_manager._initialized:
            log_manager.cleanup()
        log_manager._initialized = False
        log_manager.timezone_formatter = None
        log_manager.config = None
        log_manager._app_name = "testapp"

        # 创建日志目录
        log_path = Path(self.config.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        if self.PRINT_DEBUG:
            self._debug_print(f"\n[TEST DEBUG] 日志目录: {log_path}")
            self._debug_print(f"[TEST DEBUG] 目录是否存在: {log_path.exists()}")
            self._debug_print(
                f"[TEST DEBUG] 目录权限: {oct(log_path.stat().st_mode)[-3:] if log_path.exists() else 'N/A'}")

        if self.config.use_concurrent:
            lock_dir = Path(self.config.concurrent_lock_dir)
            lock_dir.mkdir(parents=True, exist_ok=True)
            if self.PRINT_DEBUG:
                self._debug_print(f"[TEST DEBUG] 锁目录: {lock_dir}")

        # 打印配置中的文件名
        if self.PRINT_DEBUG:
            self._debug_print(
                f"[TEST DEBUG] 配置中的文件名: file={self.config.file}, error_file={self.config.error_file}")

        # 初始化
        try:
            result = log_manager.initialize(self.config)
            if self.PRINT_DEBUG:
                self._debug_print(f"[TEST DEBUG] 初始化结果: {result}")
        except Exception as e:
            if self.PRINT_DEBUG:
                self._debug_print(f"[TEST DEBUG] 初始化异常: {e}")
                import traceback
                traceback.print_exc()
            raise

        # 检查 logger 的处理器
        app_logger = logging.getLogger("testapp")
        if self.PRINT_DEBUG:
            self._debug_print(f"[TEST DEBUG] app_logger 处理器数量: {len(app_logger.handlers)}")

        for i, h in enumerate(app_logger.handlers):
            if self.PRINT_DEBUG:
                self._debug_print(f"[TEST DEBUG]   处理器 {i}: {type(h).__name__}")
            if hasattr(h, 'baseFilename'):
                if self.PRINT_DEBUG:
                    self._debug_print(f"[TEST DEBUG]     文件: {h.baseFilename}")
                # 根据实际生成的文件名更新配置
                if 'error' in str(h.baseFilename):
                    self.config.error_file = Path(h.baseFilename).name
                else:
                    self.config.file = Path(h.baseFilename).name

        # 设置测试请求ID
        self.test_request_id = f"TEST-{int(time.time())}"
        log_manager.set_request_id(self.test_request_id)

        # 打印最终使用的文件名
        if self.PRINT_DEBUG:
            self._debug_print(
                f"[TEST DEBUG] 最终使用的文件名: file={self.config.file}, error_file={self.config.error_file}")

        # 等待初始化完成
        time.sleep(0.2)

    def _read_json_logs(self, file_path: Path, filter_system_logs: bool = True) -> List[Dict[str, Any]]:
        """读取JSON日志文件，每行解析为字典"""
        logs = []
        if not file_path.exists():
            return logs

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        log_entry = json.loads(line)

                        # 过滤系统日志
                        if filter_system_logs:
                            message = log_entry.get("message", "")
                            if any(msg in message for msg in [
                                "初始化完成",
                                "日志系统初始化",
                                "记录器初始化"
                            ]):
                                continue

                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return logs

    def _wait_for_logs(self, file_path: Path, min_lines: int = 1, timeout: float = 3.0) -> bool:
        """等待日志文件写入指定行数"""
        start_time = time.time()

        if self.PRINT_DEBUG:
            self._debug_print(f"[TEST DEBUG] 等待文件: {file_path}")
            self._debug_print(f"[TEST DEBUG] 文件是否存在: {file_path.exists()}")

        while time.time() - start_time < timeout:
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        lines = sum(1 for _ in f)
                    if self.PRINT_DEBUG:
                        self._debug_print(f"[TEST DEBUG] 当前行数: {lines}, 目标: {min_lines}")
                    if lines >= min_lines:
                        return True
                except Exception as e:
                    if self.PRINT_DEBUG:
                        self._debug_print(f"[TEST DEBUG] 读取文件错误: {e}")
            time.sleep(0.1)

        if self.PRINT_DEBUG:
            self._debug_print(f"[TEST DEBUG] 等待超时，文件最终状态: {file_path.exists()}")
        return False

    def _get_test_logs(self, file_path: Path, message: str) -> List[Dict]:
        """获取指定消息的测试日志"""
        logs = self._read_json_logs(file_path, filter_system_logs=False)
        return [log for log in logs if log.get("message") == message]

    def _assert_log_contains(self, log_entry: Dict, expected_fields: Dict[str, Any]):
        """断言日志包含指定字段"""
        for field, expected_value in expected_fields.items():
            self.assertEqual(
                log_entry.get(field),
                expected_value,
                f"字段 '{field}' 期望值 '{expected_value}'，实际值 '{log_entry.get(field)}'"
            )

    def _get_both_filename(self, base_filename: str, suffix: str) -> str:
        """获取BOTH格式的文件名"""
        base, ext = os.path.splitext(base_filename)
        return f"{base}.{suffix}{ext}"

    def test_bootstrap_logging(self):
        """测试启动日志功能"""
        from datamind.config import LogLevel, LogFormat
        from datamind.core.logging.bootstrap import (
            bootstrap_info,
            get_bootstrap_logger,
            set_debug_mode,
            _bootstrap_handler
        )

        # 启用调试模式（强制开关）
        set_debug_mode(False)

        # 验证 bootstrap handler 已初始化
        self.assertIsNotNone(_bootstrap_handler, "bootstrap handler 未初始化")

        # 获取 bootstrap logger 并验证
        bootstrap_logger = get_bootstrap_logger()

        if self.PRINT_DEBUG:
            self._debug_print(f"\nBootstrap logger 名称: {bootstrap_logger.name}")
            self._debug_print(f"Bootstrap logger 处理器数量: {len(bootstrap_logger.handlers)}")
            self._debug_print("\n记录启动日志...")

        bootstrap_info("测试启动日志")

        # 验证缓存中有日志
        if _bootstrap_handler and hasattr(_bootstrap_handler, 'buffer'):
            buffer_size = len(_bootstrap_handler.buffer)
            if self.PRINT_DEBUG:
                self._debug_print(f"记录后缓存中的日志数量: {buffer_size}")
            self.assertGreater(buffer_size, 0, "缓存中没有日志")

        # 初始化日志管理器
        if self.PRINT_DEBUG:
            self._debug_print("\n初始化日志管理器...")

        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        # 等待日志写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file, min_lines=1))

        # 读取日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 打印所有日志便于调试
        if self.PRINT_DEBUG:
            self._debug_print(f"\n日志文件中的记录数: {len(logs)}")
            for i, log in enumerate(logs):
                logger_name = log.get('logger') or log.get('name') or 'unknown'
                self._debug_print(f"  {i}: {logger_name} - {log.get('message')}")

        # 验证bootstrap日志
        bootstrap_logs = []
        for log in logs:
            logger_name = log.get('logger') or log.get('name') or ''
            if "bootstrap" in logger_name:
                bootstrap_logs.append(log)
                if self.PRINT_DEBUG:
                    self._debug_print(f"找到 bootstrap 日志: {logger_name} - {log.get('message')}")

        if self.PRINT_DEBUG:
            self._debug_print(f"找到 {len(bootstrap_logs)} 条bootstrap日志")

        self.assertGreaterEqual(len(bootstrap_logs), 1)

    def test_app_logger(self):
        """测试应用日志器"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        # 获取应用logger
        app_logger = logging.getLogger("testapp")
        test_message = f"测试应用日志消息 {time.time()}"
        app_logger.info(test_message)

        # 等待写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file))

        # 读取日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 验证
        found = any(test_message in log.get("message", "") for log in logs)
        self.assertTrue(found, f"消息 '{test_message}' 未在日志中找到")

    def test_app_logger_with_extra(self):
        """测试带额外字段的应用日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        app_logger = logging.getLogger("testapp")
        test_message = "带额外字段的日志"

        app_logger.info(
            test_message,
            extra={
                "user_id": "alice",
                "action": "test",
                "duration": 123
            }
        )

        # 等待写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file))

        # 读取日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 验证
        test_log = None
        for log in logs:
            if log.get("message") == test_message:
                test_log = log
                break

        self.assertIsNotNone(test_log)
        self.assertEqual(test_log.get("user_id"), "alice")
        self.assertEqual(test_log.get("action"), "test")
        self.assertEqual(test_log.get("duration"), 123)

    def test_log_levels(self):
        """测试不同日志级别"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        app_logger = logging.getLogger("testapp")

        test_messages = {
            "DEBUG": "DEBUG测试消息",
            "INFO": "INFO测试消息",
            "WARNING": "WARNING测试消息",
            "ERROR": "ERROR测试消息",
            "CRITICAL": "CRITICAL测试消息"
        }

        app_logger.debug(test_messages["DEBUG"])
        app_logger.info(test_messages["INFO"])
        app_logger.warning(test_messages["WARNING"])
        app_logger.error(test_messages["ERROR"])
        app_logger.critical(test_messages["CRITICAL"])

        # 等待写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file, min_lines=5))

        # 读取日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        found_levels = {}
        for log in logs:
            message = log.get("message", "")
            level = log.get("level")
            for expected_level, expected_message in test_messages.items():
                if expected_message in message:
                    found_levels[expected_level] = level

        self.assertEqual(len(found_levels), 5, f"Found levels: {found_levels}")

    def test_json_format(self):
        """测试JSON格式日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        app_logger = logging.getLogger("testapp")
        test_message = "JSON格式测试消息"
        app_logger.info(test_message, extra={"custom_field": "custom_value"})

        # 等待写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file))

        # 读取日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 找到测试消息的日志
        test_log = None
        for log in logs:
            if log.get("message") == test_message:
                test_log = log
                break

        self.assertIsNotNone(test_log, "未找到测试日志消息")
        self.assertIn("@timestamp", test_log)
        self.assertIn("level", test_log)
        self.assertEqual(test_log.get("level"), "INFO")
        self.assertIn("request_id", test_log)
        self.assertEqual(test_log.get("request_id"), self.test_request_id)
        self.assertIn("custom_field", test_log)

    def test_text_format(self):
        """测试文本格式日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.TEXT)

        app_logger = logging.getLogger("testapp")
        test_message = "文本格式测试消息"
        app_logger.info(test_message)

        # 等待写入
        log_file = self.log_dir / self.config.file
        self.assertTrue(self._wait_for_logs(log_file, min_lines=1))

        with open(log_file, 'r') as f:
            content = f.read()

        self.assertIn(test_message, content)
        self.assertIn("INFO", content)
        self.assertIn(self.test_request_id, content)

    def test_both_formats(self):
        """测试同时输出两种格式"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.BOTH
        )

        app_logger = logging.getLogger("testapp")
        test_message = "双格式测试消息"
        app_logger.info(test_message)

        # 等待写入
        time.sleep(0.5)

        # 打印所有文件用于调试
        if self.PRINT_DEBUG:
            self._debug_print(f"\n日志目录中的文件:")
            for f in self.log_dir.glob("*"):
                self._debug_print(f"  {f.name}")

        # 使用通配符查找文本文件和JSON文件
        text_files = list(self.log_dir.glob("*.text.log"))
        json_files = list(self.log_dir.glob("*.json.log"))

        self.assertGreater(len(text_files), 0, f"没有找到文本文件，可用文件: {list(self.log_dir.glob('*'))}")
        self.assertGreater(len(json_files), 0, f"没有找到JSON文件，可用文件: {list(self.log_dir.glob('*'))}")

        text_file = text_files[0]
        json_file = json_files[0]

        with open(text_file, 'r') as f:
            content = f.read()
            self.assertIn(test_message, content)

        logs = self._read_json_logs(json_file, filter_system_logs=False)
        found = any(log.get("message") == test_message for log in logs)
        self.assertTrue(found, f"消息 '{test_message}' 未在JSON日志中找到")

    def test_access_log(self):
        """测试访问日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        # 记录访问日志
        log_manager.log_access(
            method="POST",
            path="/api/users",
            status=201,
            duration_ms=150.5,
            ip="192.168.1.100",
            user_agent="Mozilla/5.0"
        )

        time.sleep(0.5)

        log_file = self.log_dir / self.config.access_log_file
        self.assertTrue(log_file.exists())

        # 获取测试日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)
        self.assertGreater(len(logs), 0, "没有找到测试日志")

        # 找到测试日志（不是系统初始化日志）
        test_log = None
        for log in logs:
            if log.get("message") == "访问日志":
                test_log = log
                break

        self.assertIsNotNone(test_log, "未找到访问日志消息")

        # 验证字段
        self.assertEqual(test_log.get("method"), "POST")
        self.assertEqual(test_log.get("path"), "/api/users")
        self.assertEqual(test_log.get("status"), 201)
        self.assertEqual(test_log.get("duration_ms"), 150.5)
        self.assertEqual(test_log.get("ip"), "192.168.1.100")
        self.assertEqual(test_log.get("user_agent"), "Mozilla/5.0")

    def test_audit_log(self):
        """测试审计日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        log_manager.log_audit(
            action="USER_CREATE",
            user_id="alice",
            target_user="bob",
            role="admin",
            ip_address="10.0.0.1"
        )

        time.sleep(0.5)

        log_file = self.log_dir / self.config.audit_log_file
        self.assertTrue(log_file.exists())

        logs = self._read_json_logs(log_file, filter_system_logs=False)
        self.assertGreater(len(logs), 0, "没有找到测试日志")

        # 找到测试日志（不是系统初始化日志）
        test_log = None
        for log in logs:
            if log.get("message") == "审计日志":
                test_log = log
                break

        self.assertIsNotNone(test_log, "未找到审计日志消息")

        # 验证字段
        self.assertEqual(test_log.get("action"), "USER_CREATE")
        self.assertEqual(test_log.get("user_id"), "alice")
        self.assertEqual(test_log.get("target_user"), "bob")
        self.assertEqual(test_log.get("role"), "admin")
        self.assertEqual(test_log.get("ip_address"), "10.0.0.1")

    def test_performance_log(self):
        """测试性能日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        log_manager.log_performance(
            operation="database.query",
            duration_ms=45.67,
            query="SELECT * FROM users",
            rows=100,
            database="primary"
        )

        time.sleep(0.5)

        log_file = self.log_dir / self.config.performance_log_file
        self.assertTrue(log_file.exists())

        logs = self._read_json_logs(log_file, filter_system_logs=False)
        self.assertGreater(len(logs), 0, "没有找到测试日志")

        # 找到测试日志（不是系统初始化日志）
        test_log = None
        for log in logs:
            if log.get("message") == "性能日志":
                test_log = log
                break

        self.assertIsNotNone(test_log, "未找到性能日志消息")

        # 验证字段
        self.assertEqual(test_log.get("operation"), "database.query")
        self.assertEqual(test_log.get("duration_ms"), 45.67)
        self.assertEqual(test_log.get("query"), "SELECT * FROM users")
        self.assertEqual(test_log.get("rows"), 100)
        self.assertEqual(test_log.get("database"), "primary")

    def test_error_log_separate(self):
        """测试错误日志分离"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        app_logger = logging.getLogger("testapp")

        # 记录日志
        app_logger.info("普通信息")
        app_logger.error("错误信息")
        app_logger.critical("严重错误")

        # 强制刷新所有处理器
        for handler in app_logger.handlers:
            handler.flush()

        time.sleep(0.5)

        main_log = self.log_dir / self.config.file

        # 使用通配符查找所有可能的错误日志文件
        error_logs = list(self.log_dir.glob("*.error*"))

        if self.PRINT_DEBUG:
            self._debug_print(f"\n主日志文件: {main_log}, 是否存在: {main_log.exists()}")
            self._debug_print(f"找到的错误日志文件: {[f.name for f in error_logs]}")

        # 检查错误日志文件
        found_error_log = None
        error_content = ""

        for error_log in error_logs:
            with open(error_log, 'r') as f:
                content = f.read()
                if content.strip():  # 如果文件非空
                    found_error_log = error_log
                    error_content = content
                    if self.PRINT_DEBUG:
                        self._debug_print(f"{error_log.name} 内容:\n{content}")
                    break

        # 读取主日志
        main_logs = self._read_json_logs(main_log, filter_system_logs=False)
        main_messages = [log.get("message", "") for log in main_logs]

        if self.PRINT_DEBUG:
            self._debug_print(f"主日志消息: {main_messages}")

        # 验证主日志包含所有消息
        self.assertIn("普通信息", "".join(main_messages))
        self.assertIn("错误信息", "".join(main_messages))
        self.assertIn("严重错误", "".join(main_messages))

        # 验证找到了非空的错误日志文件
        self.assertIsNotNone(found_error_log, "没有找到包含内容的错误日志文件")

        # 验证错误日志包含错误信息
        self.assertIn("错误信息", error_content)
        self.assertIn("严重错误", error_content)

        # 验证错误日志不包含普通信息
        self.assertNotIn("普通信息", error_content)

    def test_request_id_propagation(self):
        """测试请求ID传播"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        request_id = f"REQ-{int(time.time())}"
        log_manager.set_request_id(request_id)

        app_logger = logging.getLogger("testapp")
        test_message = "带请求ID的消息"
        app_logger.info(test_message)

        time.sleep(0.5)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        found = False
        for log in logs:
            if log.get("message") == test_message:
                self.assertEqual(log.get("request_id"), request_id)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_context_functions(self):
        """测试上下文函数"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        request_id = f"CTX-{int(time.time())}"
        set_request_id(request_id)

        # 验证通过上下文函数获取
        self.assertEqual(get_request_id(), request_id)

        # 验证通过 log_manager 获取
        self.assertEqual(log_manager.get_request_id(), request_id)

        app_logger = logging.getLogger("testapp")
        test_message = "通过上下文设置的消息"
        app_logger.info(test_message)

        time.sleep(0.5)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        found = False
        for log in logs:
            if log.get("message") == test_message:
                self.assertEqual(log.get("request_id"), request_id)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_sensitive_masking(self):
        """测试敏感信息脱敏"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            mask_sensitive=True,
            sensitive_fields={"password", "token", "credit_card"}
        )

        app_logger = logging.getLogger("testapp")
        sensitive_data = {
            "password": "123456",
            "token": "abcdef123456",
            "credit_card": "4111111111111111",
            "normal_field": "普通信息"
        }

        message = json.dumps(sensitive_data, ensure_ascii=False)
        app_logger.info(message)

        time.sleep(0.5)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        found = False
        for log in logs:
            msg = log.get("message", "")
            if "普通信息" in msg:
                self.assertNotIn("123456", msg)
                self.assertNotIn("abcdef123456", msg)
                self.assertNotIn("4111111111111111", msg)
                self.assertIn("********", msg)
                self.assertIn("普通信息", msg)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_timezone_formatting(self):
        """测试时区格式化"""
        from datamind.config import LogLevel, LogFormat, TimeZone

        timezones = [
            (TimeZone.UTC, "UTC"),
            (TimeZone.CST, "CST"),
        ]

        for tz, tz_name in timezones:
            with self.subTest(timezone=tz_name):
                self._initialize_with_config(
                    name="testapp",
                    file="testapp.log",
                    error_file="testapp.error.log",
                    access_log_file="testapp.access.log",
                    audit_log_file="testapp.audit.log",
                    performance_log_file="testapp.performance.log",
                    level=LogLevel.DEBUG,
                    format=LogFormat.JSON,
                    timezone=tz
                )

                app_logger = logging.getLogger("testapp")
                test_message = f"测试时区 {tz_name}"
                app_logger.info(test_message)

                time.sleep(0.5)

                log_file = self.log_dir / self.config.file
                logs = self._read_json_logs(log_file, filter_system_logs=False)

                found = False
                for log in logs:
                    if log.get("message") == test_message:
                        # 根据实际的时间戳格式调整验证
                        self.assertTrue(
                            "@timestamp" in log or "timestamp" in log,
                            f"日志中没有时间戳字段: {log.keys()}"
                        )
                        found = True
                        break

                self.assertTrue(found, f"未找到时区测试日志: {tz_name}")

    def test_log_rotation_by_size(self):
        """测试按大小轮转"""
        from datamind.config import LogLevel, LogFormat, RotationStrategy
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            rotation_strategy=RotationStrategy.SIZE,
            max_bytes=1024,
            backup_count=2,
            file_name_timestamp=False,
            rotation_when=None
        )

        app_logger = logging.getLogger("testapp")

        for i in range(100):
            app_logger.info(f"轮转测试消息 {i:03d} - " + "x" * 100)

        time.sleep(1)

        log_file = self.log_dir / self.config.file
        self.assertTrue(log_file.exists())

        backup_files = list(self.log_dir.glob(f"{log_file.stem}.*{log_file.suffix}"))
        self.assertGreater(len(backup_files), 0)

    def test_sampling_filter(self):
        """测试日志采样"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            sampling_rate=0.3
        )

        app_logger = logging.getLogger("testapp")

        for i in range(100):
            app_logger.info(f"采样测试消息 {i}")

        time.sleep(1)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        sampling_logs = [log for log in logs if "采样测试消息" in log.get("message", "")]

        # 应该大约有30条日志（允许一定误差）
        self.assertGreater(len(sampling_logs), 10)
        self.assertLess(len(sampling_logs), 50)

    def test_async_logging(self):
        """测试异步日志"""
        from datamind.config import LogLevel, LogFormat
        from datamind.core.logging.handlers import AsyncLogHandler

        # 使用异步配置初始化
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            use_async=True,
            async_queue_size=100
        )

        app_logger = logging.getLogger("testapp")

        # 验证异步处理器已添加
        async_handlers = [h for h in app_logger.handlers if isinstance(h, AsyncLogHandler)]

        if self.PRINT_DEBUG:
            self._debug_print(f"\n找到 {len(async_handlers)} 个异步处理器")

        self.assertGreater(len(async_handlers), 0, "没有找到异步处理器")

        # 记录日志
        for i in range(50):
            app_logger.info(f"异步测试消息 {i}")

        # 强制刷新所有异步处理器
        for handler in async_handlers:
            handler.flush()
            time.sleep(0.1)

        # 给异步处理更多时间
        time.sleep(3)

        # 使用正确的文件路径
        log_file = self.log_dir / self.config.file

        if self.PRINT_DEBUG:
            self._debug_print(f"\n日志文件: {log_file}, 是否存在: {log_file.exists()}")
            self._debug_print("日志目录中的所有文件:")
            for f in self.log_dir.glob("*"):
                self._debug_print(f"  {f.name}")

        self.assertTrue(log_file.exists(), f"日志文件不存在: {log_file}")

        # 读取所有日志
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 统计异步测试消息
        async_logs = [log for log in logs if "异步测试消息" in log.get("message", "")]

        if self.PRINT_DEBUG:
            self._debug_print(f"找到 {len(async_logs)} 条异步测试消息")

        self.assertEqual(len(async_logs), 50)

    def test_concurrent_logging(self):
        """测试并发日志"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            use_concurrent=True,
            concurrent_lock_dir=str(self.log_dir / "locks")
        )

        def write_logs(thread_id):
            app_logger = logging.getLogger("testapp")
            for i in range(5):
                app_logger.info(f"线程{thread_id} 消息 {i}")
                time.sleep(0.01)

        threads = []
        for i in range(5):
            t = threading.Thread(target=write_logs, args=(i,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(1)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        concurrent_logs = [log for log in logs if "线程" in log.get("message", "")]
        self.assertEqual(len(concurrent_logs), 25)

    def test_cleanup_manager(self):
        """测试清理管理器"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            archive_enabled=True,
            archive_path=str(self.log_dir / "archive"),
            retention_days=1,
            cleanup_at_time="23:59"
        )

        self.assertIsNotNone(log_manager.cleanup_manager)
        self.assertIsNotNone(log_manager.cleanup_manager._cleanup_thread)

    def test_watch_config_changes(self):
        """测试配置监控"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        watcher = log_manager.watch_config_changes(interval=1)
        self.assertIsNotNone(watcher)
        self.assertTrue(watcher.is_alive())

        time.sleep(2)

    def test_reload_config(self):
        """测试配置热重载"""
        from datamind.config import LogLevel, LogFormat

        # 初始化DEBUG级别
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        time.sleep(0.2)

        # 创建新配置（ERROR级别）
        new_config = self._create_base_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.ERROR,
            format=LogFormat.JSON,
            log_dir=str(self.log_dir)
        )

        # 执行重载前，保存旧的logger
        old_logger = logging.getLogger("testapp")

        if self.PRINT_DEBUG:
            self._debug_print(f"\n重载前logger级别: {logging.getLevelName(old_logger.level)}")

        # 加载新配置
        result = log_manager.reload_config(new_config)
        self.assertTrue(result)

        time.sleep(0.2)

        # 获取重载后的logger
        app_logger = logging.getLogger("testapp")

        # 验证logger的级别是否正确
        if self.PRINT_DEBUG:
            self._debug_print(f"重载后logger级别: {logging.getLevelName(app_logger.level)}")
            self._debug_print(f"重载后logger处理器数量: {len(app_logger.handlers)}")

        self.assertEqual(app_logger.level, logging.ERROR, "logger级别应该为ERROR")

        # 写入日志
        app_logger.info("这条消息不应该被记录")
        app_logger.error("这条消息应该被记录")

        # 强制刷新
        for handler in app_logger.handlers:
            handler.flush()

        time.sleep(0.5)

        log_file = self.log_dir / self.config.file
        logs = self._read_json_logs(log_file, filter_system_logs=False)

        # 打印所有日志用于调试
        if self.PRINT_DEBUG:
            self._debug_print(f"\n重载后日志文件中的记录数: {len(logs)}")
            for i, log in enumerate(logs):
                self._debug_print(f"  {i}: {log.get('level')} - {log.get('message')}")

        # 过滤出测试消息（排除系统日志）
        info_messages = [log for log in logs
                         if log.get("level") == "INFO"
                         and "不应该" in log.get("message", "")
                         and "初始化完成" not in log.get("message", "")]

        error_messages = [log for log in logs
                          if log.get("level") == "ERROR"
                          and "应该" in log.get("message", "")
                          and "初始化完成" not in log.get("message", "")]

        if self.PRINT_DEBUG:
            self._debug_print(f"INFO消息数量: {len(info_messages)}")
            self._debug_print(f"ERROR消息数量: {len(error_messages)}")

        # 验证
        self.assertEqual(len(info_messages), 0, "不应该有INFO级别的消息")
        self.assertEqual(len(error_messages), 1, "应该有一条ERROR级别的消息")

    def test_logging_performance(self):
        """测试日志性能"""
        from datamind.config import LogLevel, LogFormat
        self._initialize_with_config(
            name="testapp",
            file="testapp.log",
            error_file="testapp.error.log",
            access_log_file="testapp.access.log",
            audit_log_file="testapp.audit.log",
            performance_log_file="testapp.performance.log",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON)

        app_logger = logging.getLogger("testapp")
        start_time = time.time()
        count = 1000

        for i in range(count):
            app_logger.info(f"性能测试消息 {i}")

        time.sleep(0.5)

        duration = time.time() - start_time
        ops_per_second = count / duration

        if self.PRINT_DEBUG:
            self._debug_print(f"性能: {ops_per_second:.0f} 条/秒")
        self.assertGreater(ops_per_second, 100, f"性能太低: {ops_per_second:.0f} 条/秒")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main(verbosity=2)