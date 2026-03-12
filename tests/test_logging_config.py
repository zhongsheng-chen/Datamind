import os
import unittest
import tempfile
from pathlib import Path

from config.logging_config import LoggingConfig


def write_env(file_path: Path, content: str):
    """写入 .env 文件"""
    file_path.write_text(content.strip() + "\n")


class TestLoggingConfig(unittest.TestCase):

    def test_load_env_file(self):
        """测试读取 .env"""

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

    def test_environment_mapping(self):
        """测试 ENVIRONMENT -> .env.{env}"""

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

            del os.environ["ENVIRONMENT"]

    def test_env_file_parameter(self):
        """测试 env_file 参数"""

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
        """测试 .env.local 覆盖"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            env_file = tmp_path / ".env"
            env_local = tmp_path / ".env.local"

            write_env(
                env_file,
                """
DATAMIND_LOG_LEVEL=INFO
"""
            )

            write_env(
                env_local,
                """
DATAMIND_LOG_LEVEL=DEBUG
"""
            )

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.level.value, "DEBUG")

    def test_log_directory_creation(self):
        """测试日志目录自动创建"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            env_file = tmp_path / ".env"

            write_env(
                env_file,
                """
DATAMIND_LOG_FILE=logs/app.log
"""
            )

            config = LoggingConfig.load(base_dir=tmp_path)

            log_dir = tmp_path / "logs"

            self.assertTrue(log_dir.exists())

    # ----------------------------
    # 新增测试
    # ----------------------------

    def test_default_values(self):
        """测试默认配置"""

        config = LoggingConfig()

        self.assertIsNotNone(config.level)
        self.assertIsNotNone(config.name)

    def test_env_priority(self):
        """
        测试优先级

        env_file > ENVIRONMENT > .env
        """

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            write_env(tmp_path / ".env", "DATAMIND_LOG_LEVEL=INFO")
            write_env(tmp_path / ".env.test", "DATAMIND_LOG_LEVEL=WARNING")
            write_env(tmp_path / "custom.env", "DATAMIND_LOG_LEVEL=ERROR")

            os.environ["ENVIRONMENT"] = "test"

            config = LoggingConfig.load(
                env_file=str(tmp_path / "custom.env"),
                base_dir=tmp_path
            )

            self.assertEqual(config.level.value, "ERROR")

            del os.environ["ENVIRONMENT"]

    def test_production_mapping(self):
        """测试 production / prod 映射"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            write_env(
                tmp_path / ".env.prod",
                "DATAMIND_LOG_LEVEL=CRITICAL"
            )

            os.environ["ENVIRONMENT"] = "prod"

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.level.value, "CRITICAL")

            del os.environ["ENVIRONMENT"]

    def test_absolute_log_path(self):
        """测试绝对路径日志文件"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            log_path = tmp_path / "app.log"

            write_env(
                tmp_path / ".env",
                f"""
DATAMIND_LOG_FILE={log_path}
"""
            )

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(Path(config.file), log_path)

    def test_reload(self):
        """测试 reload 方法"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            env_file = tmp_path / ".env"

            write_env(env_file, "DATAMIND_LOG_LEVEL=INFO")

            config = LoggingConfig.load(base_dir=tmp_path)

            self.assertEqual(config.level.value, "INFO")

            write_env(env_file, "DATAMIND_LOG_LEVEL=DEBUG")

            new_config = config.reload()

            self.assertEqual(new_config.level.value, "DEBUG")

    def test_invalid_sampling_rate(self):
        """测试非法 sampling_rate"""

        with self.assertRaises(ValueError):
            LoggingConfig(DATAMIND_LOG_SAMPLING_RATE=1.5)


if __name__ == "__main__":
    unittest.main()