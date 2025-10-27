import unittest
import tempfile
from pathlib import Path
import yaml
import os
from src.config_parser import Config, BusinessWorkflow, WorkflowStep


class TestConfigParser(unittest.TestCase):

    def setUp(self):
        """在临时目录创建一个测试用 config.yaml"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.yaml"

        self.sample_config = {
            "databases": {
                "oracle": {"host": "192.168.0.1", "user": "admin", "password": "secret"},
                "postgres": {"host": "localhost", "user": "pg_user", "password": "pg_secret"}
            },
            "logging": {"name": "TestLogger", "level": "INFO", "file": "logs/test.log"},
            "features": {"demo_features": ["age", "income", "loan_amount"]},
            "models": {
                "scoring": [
                    {"model_name": "demo_lr", "model_type": "logistic_regression", "framework": "sklearn"}
                ],
                "fraud": [
                    {"model_name": "demo_fraud", "model_type": "catboost", "framework": "catboost"}
                ]
            },
            "workflows": {
                "demo_workflow": {
                    "business_name": "loan",
                    "description": "测试流程",
                    "models": [{"model_name": "demo_lr", "ab_test": {"group": "A", "weight": 0.6}}],
                    "workflow_steps": [
                        {"step_name": "rule_check", "modules": [{"name": "Basic Eligibility", "enabled": True}]},
                        {"step_name": "model_scoring"}
                    ]
                }
            }
        }

        # 写入临时 config.yaml
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.sample_config, f, allow_unicode=True)

        # 初始化 Config 对象
        self.config = Config(cfg_path=str(self.config_path))

    def tearDown(self):
        """清理临时目录"""
        self.temp_dir.cleanup()

    def test_load_config(self):
        """测试配置加载"""
        self.assertIsInstance(self.config._cfg_data, dict)
        self.assertIn("databases", self.config._cfg_data)
        self.assertIn("features", self.config._cfg_data)
        self.assertIn("models", self.config._cfg_data)
        self.assertIn("workflows", self.config._cfg_data)

    def test_get_section_and_key(self):
        """测试 get(section) 和 get(section, key)"""
        dbs = self.config.get("databases")
        self.assertIn("oracle", dbs)
        oracle = self.config.get("databases", "oracle")
        self.assertEqual(oracle["host"], "192.168.0.1")

    def test_get_features(self):
        """测试 get_features"""
        features = self.config.get_features("demo_features")
        self.assertEqual(features, ["age", "income", "loan_amount"])

    def test_get_model(self):
        """测试 get_model"""
        model = self.config.get_model("demo_lr")
        self.assertIsNotNone(model)
        self.assertEqual(model["model_type"], "logistic_regression")
        # 不存在的模型
        self.assertIsNone(self.config.get_model("non_exist_model"))

    def test_business_workflow_access(self):
        """测试 BusinessWorkflow 封装"""
        wf: BusinessWorkflow = self.config.get_business_workflow("demo_workflow")
        self.assertEqual(wf.name, "loan")
        self.assertEqual(wf.description, "测试流程")
        steps = wf.steps
        self.assertEqual(len(steps), 2)
        self.assertIsInstance(steps[0], WorkflowStep)
        self.assertEqual(steps[0].name, "rule_check")
        self.assertEqual(steps[0].modules[0]["name"], "Basic Eligibility")

    def test_workflow_models_and_ab_test(self):
        """测试 workflow 中模型解析和 AB 测试信息"""
        wf: BusinessWorkflow = self.config.get_business_workflow("demo_workflow")
        models = wf.get_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_name"], "demo_lr")
        ab_info = wf.get_ab_test_info()
        self.assertIn("demo_lr", ab_info)
        self.assertEqual(ab_info["demo_lr"]["group"], "A")

    def test_list_business_workflows(self):
        """测试列出所有 workflow"""
        names = self.config.list_business_workflows()
        self.assertIn("demo_workflow", names)

    def test_repr_safety(self):
        """测试 __repr__ 不泄露密码"""
        repr_str = repr(self.config)
        self.assertIn("***", repr_str)
        self.assertNotIn("secret", repr_str)


if __name__ == "__main__":
    unittest.main()
