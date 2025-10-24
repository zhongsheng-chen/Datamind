import unittest
import tempfile
import os
import yaml
from pathlib import Path
from src.config_parser import Config

class TestConfig(unittest.TestCase):

    def setUp(self):
        """在临时目录创建一个测试用 config.yaml"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.yaml"

        self.sample_config = {
            "databases": {
                "oracle": {
                    "host": "192.168.0.1",
                    "user": "admin",
                    "password": "secret"
                },
                "postgres": {
                    "host": "localhost",
                    "user": "pg_user",
                    "password": "pg_secret"
                }
            },
            "logging": {
                "name": "TestLogger",
                "level": "INFO",
                "file": "logs/test.log"
            },
            "models_catalog": {
                "scoring": [
                    {"model_name": "demo_lr", "model_type": "logistic_regression"}
                ]
            },
            "business_workflows": {
                "demo_workflow": {
                    "description": "测试流程",
                    "rules": [
                        {
                            "kie_container_id": "loan_rule_container",
                            "enabled_categories": ["credit", "tax"]
                        }
                    ],
                    "models": [
                        {"model_name": "demo_lr"}
                    ],
                    "workflow_steps": [
                        {"step_name": "rule_check"},
                        {"step_name": "model_scoring"}
                    ]
                }
            }
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.sample_config, f, allow_unicode=True)

        # 实例化 Config 对象
        self.config = Config(config_path=self.config_path)

    def tearDown(self):
        """清理临时目录"""
        self.temp_dir.cleanup()

    def test_load_config(self):
        """测试配置加载"""
        self.assertIsInstance(self.config._config_data, dict)
        self.assertIn("databases", self.config._config_data)

    def test_get_section(self):
        """测试 get(section)"""
        dbs = self.config.get("databases")
        self.assertIn("oracle", dbs)
        self.assertEqual(dbs["oracle"]["host"], "192.168.0.1")

    def test_get_specific_key(self):
        """测试 get(section, key)"""
        host = self.config.get("databases", "oracle")["host"]
        self.assertEqual(host, "192.168.0.1")

    def test_repr_safety(self):
        """测试 __repr__ 不泄露敏感信息"""
        repr_str = repr(self.config)
        self.assertIn("***", repr_str)
        self.assertNotIn("secret", repr_str)

    def test_business_workflows_access(self):
        """测试业务流程配置结构"""
        workflows = self.config.get("business_workflows")
        wf = workflows["demo_workflow"]
        self.assertEqual(wf["description"], "测试流程")
        self.assertEqual(wf["workflow_steps"][0]["step_name"], "rule_check")

    def test_default_path_fallback(self):
        """测试当未提供路径时，能从环境变量加载"""
        os.environ["DATAMIND_CONFIG_PATH"] = str(self.config_path)
        cfg = Config()
        self.assertIn("logging", cfg._config_data)
        del os.environ["DATAMIND_CONFIG_PATH"]

if __name__ == "__main__":
    unittest.main()
