# tests/test_log_manager.py

import os
import unittest
import logging
import json
import time
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, time as dt_time

from config.logging_config import LoggingConfig, LogFormat, LogLevel, TimeZone, RotationWhen
from core.logging import log_manager
from core.logging.context import get_request_id, set_request_id


class TestLogManager(unittest.TestCase):
    """测试日志管理器"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 创建临时目录"""
        cls.test_dir = tempfile.mkdtemp(prefix="log_test_")
        cls.log_dir = Path(cls.test_dir) / "logs"
        cls.log_dir.mkdir(exist_ok=True)

    def setUp(self):
        """每个测试前的准备工作"""
        # 重置 log_manager 状态
        if hasattr(log_manager, '_initialized') and log_manager._initialized:
            log_manager.cleanup()
        log_manager._initialized = False

        # 确保没有遗留的处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

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

    def _create_base_config(self, **kwargs) -> LoggingConfig:
        """创建基础测试配置"""
        config = LoggingConfig.load()

        # 覆盖默认配置
        config.file = str(self.log_dir / "datamind.log")
        config.error_file = str(self.log_dir / "datamind.error.log")
        config.access_log_file = str(self.log_dir / "access.log")
        config.audit_log_file = str(self.log_dir / "audit.log")
        config.performance_log_file = str(self.log_dir / "performance.log")
        config.concurrent_lock_dir = str(self.log_dir / "locks")

        # 测试配置
        config.file_name_timestamp = False
        config.console_output = False
        config.archive_enabled = False
        config.use_concurrent = False
        config.rotation_when = None
        config.format = LogFormat.JSON
        config.level = LogLevel.DEBUG
        config.mask_sensitive = True
        config.sensitive_fields = ["password", "token", "credit_card"]
        config.max_bytes = 1024 * 1024
        config.backup_count = 2
        config.timezone = TimeZone.UTC

        # 应用自定义覆盖
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # 确保目录存在
        config.ensure_log_dirs(self.log_dir)

        return config

    def _initialize_with_config(self, **kwargs):
        """使用指定配置初始化日志管理器"""
        # 在测试中默认关闭所有调试输出，避免干扰
        kwargs.setdefault('manager_debug', False)
        kwargs.setdefault('handler_debug', False)
        kwargs.setdefault('formatter_debug', False)
        kwargs.setdefault('filter_debug', False)
        kwargs.setdefault('context_debug', False)
        kwargs.setdefault('cleanup_debug', False)

        # 创建新配置
        self.config = self._create_base_config(**kwargs)

        # 确保完全重置 log_manager
        if hasattr(log_manager, '_initialized') and log_manager._initialized:
            log_manager.cleanup()
        log_manager._initialized = False
        log_manager.timezone_formatter = None
        log_manager.config = None

        # 初始化
        log_manager.initialize(self.config)

        # 设置测试请求ID
        self.test_request_id = f"TEST-{int(time.time())}"
        log_manager.set_request_id(self.test_request_id)

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
                            if message in [
                                "根日志记录器初始化完成",
                                "日志系统初始化完成",
                                "访问日志记录器初始化完成",
                                "审计日志记录器初始化完成",
                                "性能日志记录器初始化完成"
                            ]:
                                continue

                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return logs

    def _wait_for_logs(self, file_path: Path, min_lines: int = 1, timeout: float = 2.0) -> bool:
        """等待日志文件写入指定行数"""
        start_time = time.time()
        last_size = -1
        stable_count = 0

        while time.time() - start_time < timeout:
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        lines = sum(1 for _ in f)
                    if lines >= min_lines:
                        # 检查文件是否稳定（不再增长）
                        current_size = file_path.stat().st_size
                        if current_size == last_size:
                            stable_count += 1
                            if stable_count >= 3:  # 连续3次大小不变
                                return True
                        else:
                            last_size = current_size
                            stable_count = 0
                except:
                    pass
            time.sleep(0.1)
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

    # ========== 基础功能测试 ==========

    def test_initialization(self):
        """测试日志管理器初始化"""
        self._initialize_with_config()

        self.assertTrue(log_manager._initialized)
        self.assertIsNotNone(log_manager.config)
        self.assertIsNotNone(log_manager.timezone_formatter)
        self.assertIsNotNone(log_manager.request_id_filter)
        self.assertIsNotNone(log_manager.cleanup_manager)

    def test_root_logger(self):
        """测试根日志写入"""
        self._initialize_with_config()

        logger = logging.getLogger()
        test_message = f"测试根日志消息 {time.time()}"
        logger.info(test_message)

        log_file = Path(self.config.file)
        self.assertTrue(self._wait_for_logs(log_file))

        logs = self._read_json_logs(log_file)
        self.assertGreater(len(logs), 0)

        found = any(test_message in log.get("message", "") for log in logs)
        self.assertTrue(found, f"消息 '{test_message}' 未在日志中找到")

    def test_log_levels(self):
        """测试不同日志级别"""
        self._initialize_with_config()

        logger = logging.getLogger()

        test_messages = {
            "DEBUG": "DEBUG测试消息",
            "INFO": "INFO测试消息",
            "WARNING": "WARNING测试消息",
            "ERROR": "ERROR测试消息",
            "CRITICAL": "CRITICAL测试消息"
        }

        logger.debug(test_messages["DEBUG"])
        logger.info(test_messages["INFO"])
        logger.warning(test_messages["WARNING"])
        logger.error(test_messages["ERROR"])
        logger.critical(test_messages["CRITICAL"])

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        found_levels = {}
        for log in logs:
            message = log.get("message", "")
            level = log.get("level")
            for expected_level, expected_message in test_messages.items():
                if expected_message in message:
                    found_levels[expected_level] = level

        self.assertEqual(len(found_levels), 5, f"Found levels: {found_levels}")
        for level_name, actual_level in found_levels.items():
            self.assertEqual(actual_level, level_name,
                             f"Expected {level_name} but got {actual_level}")

    # ========== 格式测试 ==========

    def test_json_format(self):
        """测试JSON格式日志"""
        self._initialize_with_config(format=LogFormat.JSON)

        logger = logging.getLogger()
        test_message = "JSON格式测试消息"
        logger.info(test_message, extra={"custom_field": "custom_value"})

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)
        self.assertGreater(len(logs), 0)

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
        self.assertEqual(test_log.get("message"), test_message)
        self.assertIn("custom_field", test_log)

    def test_text_format(self):
        """测试文本格式日志"""
        self._initialize_with_config(format=LogFormat.TEXT)

        logger = logging.getLogger()
        test_message = "文本格式测试消息"
        logger.info(test_message)

        log_file = Path(self.config.file)
        self.assertTrue(self._wait_for_logs(log_file))

        with open(log_file, 'r') as f:
            content = f.read()

        self.assertIn(test_message, content)
        self.assertIn("INFO", content)
        self.assertIn(self.test_request_id, content)

    def test_both_formats(self):
        """测试同时输出两种格式"""
        self._initialize_with_config(
            format=LogFormat.BOTH,
            text_suffix="text",
            json_suffix="json"
        )

        logger = logging.getLogger()
        test_message = "双格式测试消息"
        logger.info(test_message)

        time.sleep(0.5)

        # 验证文本文件
        text_file = Path(self._get_both_filename(self.config.file, 'text'))
        self.assertTrue(text_file.exists())
        with open(text_file, 'r') as f:
            self.assertIn(test_message, f.read())

        # 验证JSON文件
        json_file = Path(self._get_both_filename(self.config.file, 'json'))
        self.assertTrue(json_file.exists())
        logs = self._read_json_logs(json_file)
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0].get("message"), test_message)

    # ========== 特殊日志测试 ==========

    def test_access_log(self):
        """测试访问日志"""
        self._initialize_with_config()

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

        log_file = Path(self.config.access_log_file)
        self.assertTrue(log_file.exists())

        # 使用辅助方法获取测试日志
        test_logs = self._get_test_logs(log_file, "访问日志")
        self.assertGreater(len(test_logs), 0, "没有找到测试日志")

        # 使用辅助方法验证字段
        self._assert_log_contains(test_logs[0], {
            "method": "POST",
            "path": "/api/users",
            "status": 201,
            "duration_ms": 150.5,
            "ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0",
            "message": "访问日志"
        })

    def test_audit_log(self):
        """测试审计日志"""
        self._initialize_with_config()

        log_manager.log_audit(
            action="USER_CREATE",
            user_id="alice",
            target_user="bob",
            role="admin",
            ip_address="10.0.0.1"
        )

        time.sleep(0.5)

        log_file = Path(self.config.audit_log_file)
        self.assertTrue(log_file.exists())

        # 使用辅助方法获取测试日志
        test_logs = self._get_test_logs(log_file, "审计日志")
        self.assertGreater(len(test_logs), 0, "没有找到测试日志")

        # 使用辅助方法验证字段
        self._assert_log_contains(test_logs[0], {
            "action": "USER_CREATE",
            "user_id": "alice",
            "target_user": "bob",
            "role": "admin",
            "ip_address": "10.0.0.1",
            "message": "审计日志"
        })

    def test_performance_log(self):
        """测试性能日志"""
        self._initialize_with_config()

        log_manager.log_performance(
            operation="database.query",
            duration_ms=45.67,
            query="SELECT * FROM users",
            rows=100,
            database="primary"
        )

        time.sleep(0.5)

        log_file = Path(self.config.performance_log_file)
        self.assertTrue(log_file.exists())

        # 使用辅助方法获取测试日志
        test_logs = self._get_test_logs(log_file, "性能日志")
        self.assertGreater(len(test_logs), 0, "没有找到测试日志")

        # 使用辅助方法验证字段
        self._assert_log_contains(test_logs[0], {
            "operation": "database.query",
            "duration_ms": 45.67,
            "query": "SELECT * FROM users",
            "rows": 100,
            "database": "primary",
            "message": "性能日志"
        })

    # ========== 功能测试 ==========

    def test_error_log_separate(self):
        """测试错误日志分离"""
        self._initialize_with_config()

        logger = logging.getLogger()

        logger.info("普通信息")
        logger.error("错误信息")
        logger.critical("严重错误")

        time.sleep(0.5)

        main_log = Path(self.config.file)
        error_log = Path(self.config.error_file)

        main_logs = self._read_json_logs(main_log)
        error_logs = self._read_json_logs(error_log)

        main_messages = [log.get("message", "") for log in main_logs]
        error_messages = [log.get("message", "") for log in error_logs]

        self.assertIn("普通信息", "".join(main_messages))
        self.assertIn("错误信息", "".join(main_messages))
        self.assertIn("严重错误", "".join(main_messages))

        self.assertNotIn("普通信息", "".join(error_messages))
        self.assertIn("错误信息", "".join(error_messages))
        self.assertIn("严重错误", "".join(error_messages))

    def test_request_id_propagation(self):
        """测试请求ID传播"""
        self._initialize_with_config()

        request_id = f"REQ-{int(time.time())}"
        log_manager.set_request_id(request_id)

        logger = logging.getLogger()
        test_message = "带请求ID的消息"
        logger.info(test_message)

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        found = False
        for log in logs:
            if log.get("message") == test_message:
                self.assertEqual(log.get("request_id"), request_id)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_context_functions(self):
        """测试上下文函数"""
        self._initialize_with_config()

        request_id = f"CTX-{int(time.time())}"
        set_request_id(request_id)

        # 验证通过上下文函数获取
        self.assertEqual(get_request_id(), request_id)

        # 验证通过 log_manager 获取
        self.assertEqual(log_manager.get_request_id(), request_id)

        logger = logging.getLogger()
        test_message = "通过上下文设置的消息"
        logger.info(test_message)

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        found = False
        for log in logs:
            if log.get("message") == test_message:
                self.assertEqual(log.get("request_id"), request_id)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_sensitive_masking(self):
        """测试敏感信息脱敏"""
        self._initialize_with_config(
            mask_sensitive=True,
            sensitive_fields=["password", "token", "credit_card"]
        )

        logger = logging.getLogger()
        sensitive_data = {
            "password": "123456",
            "token": "abcdef123456",
            "credit_card": "4111111111111111",
            "normal_field": "普通信息"
        }

        # 使用 json.dumps 但确保中文不被转义
        message = json.dumps(sensitive_data, ensure_ascii=False)
        logger.info(message)

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        found = False
        for log in logs:
            msg = log.get("message", "")
            if "普通信息" in msg:
                # 敏感信息应该被脱敏
                self.assertNotIn("123456", msg)
                self.assertNotIn("abcdef123456", msg)
                self.assertNotIn("4111111111111111", msg)
                # 应该出现脱敏字符
                self.assertIn("********", msg)
                # 普通字段应该保持不变
                self.assertIn("普通信息", msg)
                found = True
                break

        self.assertTrue(found, "未找到测试日志消息")

    def test_timezone_formatting(self):
        """测试时区格式化"""
        timezones = [
            (TimeZone.UTC, "UTC"),
            (TimeZone.CST, "CST"),
        ]

        for tz, tz_name in timezones:
            with self.subTest(timezone=tz_name):
                # 每次都要重新初始化
                self._initialize_with_config(timezone=tz)

                # 记录一条测试日志
                logger = logging.getLogger()
                test_message = f"测试时区 {tz_name}"
                logger.info(test_message)

                time.sleep(0.5)

                # 读取日志并验证
                log_file = Path(self.config.file)
                logs = self._read_json_logs(log_file, filter_system_logs=False)

                found = False
                for log in logs:
                    if log.get("message") == test_message:
                        # 验证时区字段
                        self.assertEqual(
                            log.get("timezone"),
                            tz_name,
                            f"Expected {tz_name} in log but got {log.get('timezone')}"
                        )
                        found = True
                        break

                self.assertTrue(found, f"未找到时区测试日志: {tz_name}")

    # ========== 高级功能测试 ==========

    def test_log_rotation_by_size(self):
        """测试按大小轮转"""
        self._initialize_with_config(
            max_bytes=1024,
            backup_count=2,
            file_name_timestamp=False,
            rotation_when=None
        )

        logger = logging.getLogger()

        for i in range(100):
            logger.info(f"轮转测试消息 {i:03d} - " + "x" * 100)

        time.sleep(1)

        log_file = Path(self.config.file)
        self.assertTrue(log_file.exists())

        backup_files = list(self.log_dir.glob(f"{log_file.stem}.*{log_file.suffix}"))
        self.assertGreater(len(backup_files), 0)

    def test_sampling_filter(self):
        """测试日志采样"""
        self._initialize_with_config(
            sampling_rate=0.3,
            sampling_interval=0,
            rotation_when=None
        )

        logger = logging.getLogger()

        for i in range(100):
            logger.info(f"采样测试消息 {i}")

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        # 过滤出采样测试消息
        sampling_logs = [log for log in logs if "采样测试消息" in log.get("message", "")]

        # 应该大约有30条日志（允许一定误差）
        self.assertGreater(len(sampling_logs), 10)
        self.assertLess(len(sampling_logs), 50)

    def test_async_logging(self):
        """测试异步日志"""
        self._initialize_with_config(
            use_async=True,
            async_queue_size=100,
            rotation_when=None
        )

        logger = logging.getLogger()

        for i in range(50):
            logger.info(f"异步测试消息 {i}")

        time.sleep(1)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        # 过滤出异步测试消息
        async_logs = [log for log in logs if "异步测试消息" in log.get("message", "")]
        self.assertEqual(len(async_logs), 50)

    def test_concurrent_logging(self):
        """测试并发日志"""
        self._initialize_with_config(
            use_concurrent=True,
            concurrent_lock_dir=str(self.log_dir / "locks"),
            rotation_when=None
        )

        import threading

        def write_logs(thread_id):
            logger = logging.getLogger(f"thread.{thread_id}")
            for i in range(5):
                logger.info(f"线程{thread_id} 消息 {i}")
                time.sleep(0.01)

        threads = []
        for i in range(5):
            t = threading.Thread(target=write_logs, args=(i,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(1)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        # 过滤出并发测试消息
        concurrent_logs = [log for log in logs if "线程" in log.get("message", "")]
        self.assertEqual(len(concurrent_logs), 25)

    def test_cleanup_manager(self):
        """测试清理管理器"""
        self._initialize_with_config(
            archive_enabled=True,
            archive_path=str(self.log_dir / "archive"),
            retention_days=1,
            cleanup_at_time="23:59"
        )

        self.assertIsNotNone(log_manager.cleanup_manager)
        # 验证清理管理器已启动
        self.assertIsNotNone(log_manager.cleanup_manager._cleanup_thread)

    def test_watch_config_changes(self):
        """测试配置监控"""
        self._initialize_with_config()

        # 启动监控
        watcher = log_manager.watch_config_changes(interval=1)
        self.assertIsNotNone(watcher)
        self.assertTrue(watcher.is_alive())

        # 等待一下
        time.sleep(2)

    def test_reload_config(self):
        """测试配置热重载"""
        # 先初始化一个配置
        self._initialize_with_config(level=LogLevel.INFO)

        time.sleep(0.2)

        # 创建新配置
        new_config = self._create_base_config(level=LogLevel.ERROR)

        # 执行重载
        result = log_manager.reload_config(new_config)
        self.assertTrue(result)
        self.assertEqual(log_manager.config.level, LogLevel.ERROR)

        time.sleep(0.2)

        # 写入日志
        logger = logging.getLogger()
        logger.info("这条消息不应该被记录")
        logger.error("这条消息应该被记录")

        time.sleep(0.5)

        log_file = Path(self.config.file)
        logs = self._read_json_logs(log_file)

        info_messages = [log for log in logs if log.get("level") == "INFO" and "不应该" in log.get("message", "")]
        error_messages = [log for log in logs if log.get("level") == "ERROR" and "应该" in log.get("message", "")]

        self.assertEqual(len(info_messages), 0)
        self.assertEqual(len(error_messages), 1)

    # ========== 性能测试 ==========

    def test_logging_performance(self):
        """测试日志性能"""
        self._initialize_with_config()

        logger = logging.getLogger()
        start_time = time.time()
        count = 1000

        for i in range(count):
            logger.info(f"性能测试消息 {i}")

        duration = time.time() - start_time
        ops_per_second = count / duration

        # 可以根据需要调整阈值
        self.assertGreater(ops_per_second, 100, f"性能太低: {ops_per_second:.0f} 条/秒")


if __name__ == "__main__":
    # 设置日志级别，减少测试时的干扰输出
    logging.basicConfig(level=logging.WARNING)
    unittest.main(verbosity=2)