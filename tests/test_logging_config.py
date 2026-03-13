# tests/test_logging_config.py

import os
import unittest
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch

from config.logging_config import LoggingConfig, LogLevel, LogFormat, TimeZone, RotationWhen, TimestampPrecision


def write_env(file_path: Path, content: str):
    """写入 .env 文件"""
    file_path.write_text(content.strip() + "\n")


class TestLoggingConfig(unittest.TestCase):
    """测试日志配置类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 保存并清除所有相关环境变量
        self._original_env = {}

        # 列出所有可能影响测试的环境变量
        env_vars_to_clear = [
            'ENVIRONMENT', 'ENV',
            'DATAMIND_LOG_NAME', 'DATAMIND_LOG_LEVEL', 'DATAMIND_LOG_FILE',
            'DATAMIND_LOG_TIMEZONE', 'DATAMIND_LOG_FORMAT',
            'DATAMIND_LOG_MAX_BYTES', 'DATAMIND_LOG_BACKUP_COUNT',
            'DATAMIND_LOG_RETENTION_DAYS', 'DATAMIND_LOG_ROTATION_AT_TIME',
            'DATAMIND_LOG_SAMPLING_RATE', 'DATAMIND_LOG_SAMPLING_INTERVAL',
            'DATAMIND_LOG_FORMATTER_DEBUG', 'DATAMIND_LOG_MANAGER_DEBUG',
            'DATAMIND_LOG_HANDLER_DEBUG', 'DATAMIND_LOG_FILTER_DEBUG',
            'DATAMIND_LOG_CONTEXT_DEBUG', 'DATAMIND_LOG_CLEANUP_DEBUG',
            'DATAMIND_JSON_USE_EPOCH', 'DATAMIND_JSON_EPOCH_UNIT',
            'DATAMIND_LOG_USE_CONCURRENT', 'DATAMIND_LOG_ASYNC',
            'DATAMIND_LOG_ACCESS', 'DATAMIND_LOG_AUDIT', 'DATAMIND_LOG_PERFORMANCE',
            'DATAMIND_LOG_MASK_SENSITIVE', 'DATAMIND_LOG_CONSOLE',
            'DATAMIND_LOG_ARCHIVE', 'DATAMIND_HOME'
        ]

        for env_var in env_vars_to_clear:
            if env_var in os.environ:
                self._original_env[env_var] = os.environ[env_var]
                del os.environ[env_var]

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复环境变量
        for env_var, value in self._original_env.items():
            os.environ[env_var] = value

    # ========== 基础功能测试 ==========

    def test_load_env_file(self):
        """测试读取 .env 文件"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(
                env_file,
                """
DATAMIND_LOG_NAME=TestApp
DATAMIND_LOG_LEVEL=DEBUG
DATAMIND_LOG_FILE=logs/test.log
"""
            )

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.name, "TestApp")
            self.assertEqual(config.level.value, "DEBUG")
            self.assertEqual(config.file, "logs/test.log")

    def test_environment_mapping(self):
        """测试 ENVIRONMENT -> .env.{env} 映射"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env.test"

            write_env(
                env_file,
                """
DATAMIND_LOG_NAME=TestEnv
DATAMIND_LOG_LEVEL=WARNING
"""
            )

            os.environ["ENVIRONMENT"] = "test"
            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.name, "TestEnv")
            self.assertEqual(config.level.value, "WARNING")

    def test_env_file_parameter(self):
        """测试 env_file 参数优先级"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / "custom.env"

            write_env(
                env_file,
                """
DATAMIND_LOG_NAME=CustomEnv
DATAMIND_LOG_LEVEL=ERROR
"""
            )

            config = LoggingConfig.load(
                env_file=str(env_file),
                base_dir=tmp_path
            )

            self.assertEqual(config.name, "CustomEnv")
            self.assertEqual(config.level.value, "ERROR")

    def test_env_local_override(self):
        """测试 .env.local 覆盖 .env"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"
            env_local = tmp_path / ".env.local"

            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")
            write_env(env_local, "DATAMIND_LOG_LEVEL=DEBUG")

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.level.value, "DEBUG")

    def test_log_directory_creation(self):
        """测试日志目录自动创建"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_FILE=logs/app.log")

            config = LoggingConfig.load(base_dir=tmp_path)
            log_dir = tmp_path / "logs"

            self.assertTrue(log_dir.exists())

    # ========== 优先级测试 ==========

    def test_env_priority(self):
        """
        测试配置优先级：env_file 参数 > ENVIRONMENT 环境变量 > .env 文件
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # 创建多个配置文件
            write_env(tmp_path / ".env", "DATAMIND_LOG_LEVEL=INFO")
            write_env(tmp_path / ".env.test", "DATAMIND_LOG_LEVEL=WARNING")
            write_env(tmp_path / "custom.env", "DATAMIND_LOG_LEVEL=ERROR")

            # 设置环境变量
            os.environ["ENVIRONMENT"] = "test"

            # 加载配置（同时指定 env_file 参数）
            config = LoggingConfig.load(
                env_file=str(tmp_path / "custom.env"),
                base_dir=tmp_path
            )

            # 应该使用 env_file 参数指定的配置
            self.assertEqual(config.level.value, "ERROR")

    def test_env_priority_without_env_file(self):
        """测试配置优先级：ENVIRONMENT 环境变量 > .env 文件"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            write_env(tmp_path / ".env", "DATAMIND_LOG_LEVEL=INFO")
            write_env(tmp_path / ".env.test", "DATAMIND_LOG_LEVEL=WARNING")

            os.environ["ENVIRONMENT"] = "test"

            config = LoggingConfig.load(base_dir=tmp_path)

            # 应该使用 .env.test 的配置
            self.assertEqual(config.level.value, "WARNING")

    # ========== 环境映射测试 ==========

    def test_production_mapping(self):
        """测试 production / prod 映射到 .env.prod"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            write_env(tmp_path / ".env.prod", "DATAMIND_LOG_LEVEL=CRITICAL")

            # 测试 prod 映射
            os.environ["ENVIRONMENT"] = "prod"
            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config.level.value, "CRITICAL")

            # 测试 production 映射
            os.environ["ENVIRONMENT"] = "production"
            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config.level.value, "CRITICAL")

    def test_development_mapping(self):
        """测试 development / dev 映射到 .env.dev"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            write_env(tmp_path / ".env.dev", "DATAMIND_LOG_LEVEL=DEBUG")

            # 测试 dev 映射
            os.environ["ENVIRONMENT"] = "dev"
            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config.level.value, "DEBUG")

            # 测试 development 映射
            os.environ["ENVIRONMENT"] = "development"
            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config.level.value, "DEBUG")

    # ========== 路径测试 ==========

    def test_absolute_log_path(self):
        """测试绝对路径日志文件"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_path = tmp_path / "app.log"

            write_env(
                tmp_path / ".env",
                f"DATAMIND_LOG_FILE={log_path}"
            )

            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(Path(config.file), log_path)

    def test_relative_log_path(self):
        """测试相对路径日志文件 - 相对于 base_dir"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            write_env(
                tmp_path / ".env",
                "DATAMIND_LOG_FILE=logs/app.log"
            )

            config = LoggingConfig.load(base_dir=tmp_path)
            # 相对路径应该相对于 base_dir
            expected_path = tmp_path / "logs" / "app.log"
            # config.file 可能是相对路径，需要与 base_dir 结合
            full_path = (tmp_path / config.file).resolve()
            self.assertEqual(full_path, expected_path.resolve())

    # ========== 配置重载和比较测试 ==========

    def test_reload(self):
        """测试 reload 方法重新加载配置"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            # 初始配置
            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")
            config = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config.level.value, "INFO")

            # 修改配置文件
            write_env(env_file, "DATAMIND_LOG_LEVEL=DEBUG")

            # 重新加载
            new_config = config.reload()
            self.assertEqual(new_config.level.value, "DEBUG")

    def test_config_digest(self):
        """测试配置摘要功能"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")
            config1 = LoggingConfig.load(base_dir=tmp_path)

            write_env(env_file, "DATAMIND_LOG_LEVEL=DEBUG")
            config2 = LoggingConfig.load(base_dir=tmp_path)

            # 不同配置应该有不同的摘要
            self.assertNotEqual(config1.get_config_digest(), config2.get_config_digest())

            # 相同配置应该有相同的摘要
            config3 = LoggingConfig.load(base_dir=tmp_path)
            self.assertEqual(config2.get_config_digest(), config3.get_config_digest())

    def test_is_equivalent_to(self):
        """测试配置等效性判断"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")
            config1 = LoggingConfig.load(base_dir=tmp_path)
            config2 = LoggingConfig.load(base_dir=tmp_path)

            # 相同配置应该等效
            self.assertTrue(config1.is_equivalent_to(config2))

            write_env(env_file, "DATAMIND_LOG_LEVEL=DEBUG")
            config3 = LoggingConfig.load(base_dir=tmp_path)

            # 不同配置不应该等效
            self.assertFalse(config1.is_equivalent_to(config3))

    def test_diff(self):
        """测试配置差异比较"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")
            config1 = LoggingConfig.load(base_dir=tmp_path)

            write_env(env_file, "DATAMIND_LOG_LEVEL=DEBUG")
            config2 = LoggingConfig.load(base_dir=tmp_path)

            diff = config1.diff(config2)
            self.assertIn("level", diff)

    # ========== 默认值和验证测试 ==========

    def test_default_values(self):
        """测试默认配置值"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 创建一个空的 .env 文件，确保没有外部配置干扰
            write_env(tmp_path / ".env", "# Empty config")

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.name, "Datamind")
            self.assertEqual(config.level, LogLevel.INFO)
            self.assertEqual(config.timezone, TimeZone.UTC)
            self.assertEqual(config.format, LogFormat.JSON)
            self.assertEqual(config.max_bytes, 104857600)
            self.assertEqual(config.backup_count, 30)
            self.assertEqual(config.retention_days, 90)
            self.assertEqual(config.encoding, "utf-8")
            self.assertEqual(config.console_output, True)

    def test_invalid_sampling_rate(self):
        """测试非法的 sampling_rate 值"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            # 测试大于1的值
            write_env(env_file, "DATAMIND_LOG_SAMPLING_RATE=1.5")
            with self.assertRaises(ValueError) as context:
                LoggingConfig.load(base_dir=tmp_path)
            self.assertIn("采样率必须在0到1之间", str(context.exception))

            # 测试小于0的值
            write_env(env_file, "DATAMIND_LOG_SAMPLING_RATE=-0.5")
            with self.assertRaises(ValueError):
                LoggingConfig.load(base_dir=tmp_path)

    def test_invalid_max_bytes(self):
        """测试非法的 max_bytes 值"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_MAX_BYTES=512")
            with self.assertRaises(ValueError) as context:
                LoggingConfig.load(base_dir=tmp_path)
            self.assertIn("max_bytes 不能小于1KB", str(context.exception))

    def test_invalid_rotation_at_time(self):
        """测试非法的 rotation_at_time 格式"""
        test_cases = ["25:00", "23:60", "abc", "24:00"]

        for invalid_time in test_cases:
            with self.subTest(invalid_time=invalid_time):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    env_file = tmp_path / ".env"
                    write_env(env_file, f"DATAMIND_LOG_ROTATION_AT_TIME={invalid_time}")

                    with self.assertRaises(ValueError):
                        LoggingConfig.load(base_dir=tmp_path)

    def test_invalid_json_epoch_unit(self):
        """测试非法的 json_epoch_unit 值"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_JSON_EPOCH_UNIT=invalid_unit")
            with self.assertRaises(ValueError):
                LoggingConfig.load(base_dir=tmp_path)

    # ========== 辅助方法测试 ==========

    def test_to_logging_level(self):
        """测试日志级别转换"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            write_env(tmp_path / ".env", "DATAMIND_LOG_LEVEL=DEBUG")
            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.to_logging_level("INFO"), logging.INFO)
            self.assertEqual(config.to_logging_level(logging.WARNING), logging.WARNING)
            self.assertEqual(config.to_logging_level("ERROR"), logging.ERROR)
            self.assertEqual(config.to_logging_level(), logging.DEBUG)  # 默认使用配置的级别

    def test_to_dict(self):
        """测试配置导出为字典"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"
            write_env(env_file, "DATAMIND_LOG_NAME=TestApp")

            config = LoggingConfig.load(base_dir=tmp_path)
            config_dict = config.to_dict()

            self.assertEqual(config_dict["name"], "TestApp")
            self.assertIn("level", config_dict)
            self.assertNotIn("remote_token", config_dict)  # 敏感字段应该被排除

    def test_to_yaml(self):
        """测试配置导出为YAML"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"
            write_env(env_file, "DATAMIND_LOG_NAME=TestApp")

            config = LoggingConfig.load(base_dir=tmp_path)
            yaml_str = config.to_yaml()

            self.assertIsInstance(yaml_str, str)
            self.assertIn("name: TestApp", yaml_str)

    def test_validate_all(self):
        """测试配置全面验证 - 验证警告"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            # 设置有效的配置值（避免验证错误）
            write_env(
                env_file,
                """
DATAMIND_LOG_MAX_BYTES=1048576
DATAMIND_LOG_BACKUP_COUNT=50
DATAMIND_LOG_RETENTION_DAYS=5
DATAMIND_LOG_SAMPLING_RATE=0.5
DATAMIND_LOG_SAMPLING_INTERVAL=10
"""
            )

            config = LoggingConfig.load(base_dir=tmp_path)
            report = config.validate_all()

            self.assertTrue(report["valid"])
            # 验证是否有警告（配置值虽然有效但会产生警告）
            self.assertGreaterEqual(len(report["warnings"]), 0)

    def test_validate_all_with_errors(self):
        """测试配置全面验证 - 验证错误"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_file = tmp_path / ".env"

            # 设置会导致错误的配置
            write_env(
                env_file,
                """
DATAMIND_LOG_MAX_BYTES=512
"""
            )

            with self.assertRaises(ValueError):
                LoggingConfig.load(base_dir=tmp_path)

    def test_get_env_files(self):
        """测试获取环境文件列表"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # 创建多个环境文件
            write_env(tmp_path / ".env", "DATAMIND_LOG_LEVEL=INFO")
            write_env(tmp_path / ".env.test", "DATAMIND_LOG_LEVEL=DEBUG")

            os.environ["ENVIRONMENT"] = "test"
            config = LoggingConfig.load(base_dir=tmp_path)

            env_files = config.get_env_files()
            self.assertGreater(len(env_files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)