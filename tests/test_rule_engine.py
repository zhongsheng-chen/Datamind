import unittest
import tempfile
import os
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
from src.rule_engine import load_latest_rule, get_rules, apply_rules

class TestRuleEngine(unittest.TestCase):

    def setUp(self):
        # 创建临时规则目录
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.rules_path = Path(self.tmp_dir.name) / "personal_loan"
        self.rules_path.mkdir(parents=True, exist_ok=True)

        # 创建两个版本规则文件
        rule_v1 = {"rules": [{"field": "age", "op": "gt", "value": 18}]}
        rule_v2 = {"rules": [{"field": "age", "op": "gt", "value": 21}]}

        with open(self.rules_path / "personal_loan_v1.yaml", "w") as f:
            yaml.safe_dump(rule_v1, f)
        with open(self.rules_path / "personal_loan_v2.yaml", "w") as f:
            yaml.safe_dump(rule_v2, f)

        # 保存原始工作目录
        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_dir.name)  # 切换当前工作目录到临时目录

    def tearDown(self):
        os.chdir(self.original_cwd)  # 恢复工作目录
        self.tmp_dir.cleanup()

    def test_load_latest_rule(self):
        """测试 load_latest_rule 获取最新规则文件"""
        latest_file = load_latest_rule("personal_loan")
        self.assertTrue(latest_file.endswith("personal_loan_v2.yaml"))

    def test_get_rules(self):
        """测试 get_rules 函数"""
        file = self.rules_path / "personal_loan_v1.yaml"
        with open(file) as f:
            data = f.read()
        with patch("builtins.open", mock_open(read_data=data)):
            rules = get_rules("personal_loan", version="v1")
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["field"], "age")
        self.assertEqual(rules[0]["op"], "gt")
        self.assertEqual(rules[0]["value"], 18)

    def test_apply_rules(self):
        """测试 apply_rules 函数"""
        rules = [{"field": "age", "op": "gt", "value": 21}]
        # 不通过
        result, msg = apply_rules(rules, {"age": 20})
        self.assertFalse(result)
        self.assertEqual(msg, "age <= 21")
        # 通过
        result, msg = apply_rules(rules, {"age": 25})
        self.assertTrue(result)
        self.assertEqual(msg, "pass")

if __name__ == "__main__":
    unittest.main()
