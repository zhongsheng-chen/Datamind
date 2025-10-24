import unittest
import os
import logging
from src.utils import load_config, setup_logger

class TestUtils(unittest.TestCase):

    def test_load_config(self):
        """测试 load_config 函数能正常加载 YAML 配置"""
        config = load_config("config/config.yaml")
        self.assertIsInstance(config, dict)

        self.assertIn("oracle", config)
        self.assertIn("postgres", config)
        self.assertIn("logging", config)
        self.assertIn("model_registry", config)

    def test_setup_logger(self):
        """测试 setup_logger 函数能返回正确 Logger"""
        config = load_config("config/config.yaml")
        logger = setup_logger(config)

        # logger 必须是 Logger 实例
        self.assertIsInstance(logger, logging.Logger)
        # 名称必须正确
        self.assertEqual(logger.name, "risk_service")
        # 至少有控制台和文件两个 Handler
        self.assertGreaterEqual(len(logger.handlers), 2)

        # 文件日志 Handler 的路径存在
        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )
        self.assertIsNotNone(file_handler)
        log_dir = os.path.dirname(file_handler.baseFilename)
        self.assertTrue(os.path.isdir(log_dir))

if __name__ == "__main__":
    unittest.main()
