# tests/test_log_manager.py

import os
import unittest
import logging
import json
from pathlib import Path
from time import sleep
from config.logging_config import LoggingConfig, LogFormat, LogLevel
from core.log_manager import log_manager


class TestLogManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 创建日志目录并初始化日志管理器"""
        cls.log_dir = Path("logs_test_unittest")
        cls.log_dir.mkdir(exist_ok=True)

        # 使用 load() 加载配置，避免 extra_forbid 错误
        cls.config = LoggingConfig.load()

        # 覆盖默认日志路径到测试目录
        cls.config.file = str(cls.log_dir / "datamind.log")
        cls.config.error_file = str(cls.log_dir / "datamind.error.log")
        cls.config.access_log_file = str(cls.log_dir / "access.log")
        cls.config.audit_log_file = str(cls.log_dir / "audit.log")
        cls.config.performance_log_file = str(cls.log_dir / "performance.log")

        # 测试时禁用文件名时间戳，这样文件名就是固定的
        cls.config.file_name_timestamp = False

        # 可选：覆盖一些测试特定配置
        cls.config.format = LogFormat.JSON
        cls.config.level = LogLevel.DEBUG
        cls.config.console_output = False
        cls.config.archive_enabled = False
        cls.config.mask_sensitive = True
        cls.config.sensitive_fields = ["password", "token"]
        cls.config.max_bytes = 1024 * 1024
        cls.config.backup_count = 3

        # 确保目录存在
        cls.config.ensure_log_dirs(cls.log_dir)

        log_manager.initialize(cls.config)
        log_manager.set_request_id("UNITTEST-001")

    @classmethod
    def tearDownClass(cls):
        """测试完成后清理日志文件"""
        log_manager.cleanup()
        # 只删除文件，不删除目录
        for f in cls.log_dir.glob("*"):
            if f.is_file():  # 只删除文件
                f.unlink()
        # 最后删除空目录
        try:
            cls.log_dir.rmdir()
        except OSError:
            # 如果目录非空，就不删除
            pass

    def read_json_logs(self, file_path):
        """读取JSON日志文件，每行解析为字典"""
        logs = []
        if not os.path.exists(file_path):
            print(f"警告: 文件不存在 {file_path}")  # 添加调试信息
            return logs
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"JSON解析错误: {e}, 行内容: {line}")
                        continue
        print(f"从 {file_path} 读取了 {len(logs)} 条日志")  # 添加调试信息
        return logs

    def find_latest_log_file(self, pattern):
        """查找最新的日志文件"""
        log_files = list(self.log_dir.glob(f"{pattern}*"))
        if not log_files:
            return None
        # 按修改时间排序，返回最新的
        return str(sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[0])

    def test_root_logger(self):
        """测试根日志写入"""
        logger = logging.getLogger()
        logger.info("测试根日志")
        sleep(0.5)

        # 查找最新的日志文件
        log_file = self.find_latest_log_file("datamind")
        self.assertIsNotNone(log_file, "找不到日志文件")

        logs = self.read_json_logs(log_file)
        self.assertTrue(any("测试根日志" in log.get("message", "") for log in logs))

    def test_sensitive_masking(self):
        """测试敏感信息脱敏"""
        logger = logging.getLogger()
        logger.info('包含敏感信息: {"password": "123456", "token": "abcdef"}')
        sleep(0.5)

        log_file = self.find_latest_log_file("datamind")
        self.assertIsNotNone(log_file, "找不到日志文件")

        logs = self.read_json_logs(log_file)
        found = False
        for log in logs:
            msg = log.get("message", "")
            if "password" in msg or "token" in msg:
                self.assertIn("********", msg)
                found = True
        self.assertTrue(found)

    def test_access_audit_performance_logs(self):
        """测试访问、审计、性能日志"""
        log_manager.log_access(path="/api/test", status_code=200)
        log_manager.log_audit(action="login", user_id="alice")
        log_manager.log_performance(operation="db_query", duration_ms=123.4)

        # 增加等待时间，确保日志写入
        sleep(1)

        # 验证访问日志
        self.assertTrue(os.path.exists(self.config.access_log_file),
                       f"Access log file not found: {self.config.access_log_file}")
        access_logs = self.read_json_logs(str(self.config.access_log_file))
        self.assertTrue(any(log.get("path") == "/api/test" for log in access_logs),
                       f"Expected path '/api/test' not found in access logs: {access_logs}")

        # 验证审计日志
        self.assertTrue(os.path.exists(self.config.audit_log_file),
                       f"Audit log file not found: {self.config.audit_log_file}")
        audit_logs = self.read_json_logs(str(self.config.audit_log_file))
        self.assertTrue(any(log.get("action") == "login" and log.get("user_id") == "alice" for log in audit_logs),
                       f"Expected action 'login' for user 'alice' not found in audit logs: {audit_logs}")

        # 验证性能日志
        self.assertTrue(os.path.exists(self.config.performance_log_file),
                       f"Performance log file not found: {self.config.performance_log_file}")
        performance_logs = self.read_json_logs(str(self.config.performance_log_file))
        self.assertTrue(
            any(log.get("operation") == "db_query" and log.get("duration_ms") == 123.4 for log in performance_logs),
            f"Expected operation 'db_query' with duration 123.4 not found in performance logs: {performance_logs}")


if __name__ == "__main__":
    unittest.main()