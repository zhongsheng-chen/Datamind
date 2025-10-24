#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rule_engine.py
规则执行引擎，支持统一 YAML 文件解析、各种规则类型执行
"""

import os
import yaml
from datetime import datetime, timedelta
import re
from collections import defaultdict
from src.setup import setup_logger

logger = setup_logger()

class RuleEngine:
    def __init__(self, rule_path="/tmp/pycharm_project_798/rules/demo_loan_rule_20250901.yaml", external_funcs=None):
        self.rule_path = rule_path
        self.rule_data = self._load_rules()
        self.rule_results = {}  # 存储规则执行结果
        self.external_funcs = external_funcs or {}

    def _load_rules(self):
        if not os.path.exists(self.rule_path):
            raise FileNotFoundError(f"规则文件不存在: {self.rule_path}")
        with open(self.rule_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("categories", {})

    def execute(self, applicant_data):
        """
        执行所有规则
        applicant_data: dict, 申请人相关字段，例如: {"age":25, "income":5000, "id_number":"123456..."}
        返回: dict, rule_id -> True/False
        """
        self.rule_results.clear()
        for category, groups in self.rule_data.items():
            for group, rules in groups.items():
                for rule in rules:
                    rule_id = rule["id"]
                    try:
                        result = self._execute_rule(rule, applicant_data)
                        self.rule_results[rule_id] = result
                        logger.info(f"规则 {rule_id} 执行结果: {result}")
                    except Exception as e:
                        logger.error(f"执行规则 {rule_id} 出错: {e}")
                        self.rule_results[rule_id] = False
        return self.rule_results

    def _execute_rule(self, rule, data):
        rule_type = rule.get("type")
        if rule_type == "boolean":
            return eval(rule["condition"], {}, data)
        elif rule_type == "enum":
            return eval(rule["condition"], {}, data)
        elif rule_type == "threshold":
            return eval(rule["condition"], {}, data)
        elif rule_type == "range":
            return eval(rule["condition"], {}, data)
        elif rule_type == "date":
            return eval(rule["condition"], {}, data)
        elif rule_type == "regex":
            value = data.get(rule.get("field",""), "")
            return re.match(rule["pattern"], str(value)) is not None
        elif rule_type == "aggregate":
            return eval(rule["condition"], {}, data)
        elif rule_type == "combination":
            return eval(rule["condition"], {}, data)
        elif rule_type == "probabilistic":
            return eval(rule["condition"], {}, data)
        elif rule_type == "conditional":
            # 简单 if ... then ... 解析
            cond = rule["condition"]
            if "if" in cond and "then" in cond:
                m = re.match(r"if (.+) then (.+)", cond)
                if m:
                    if eval(m.group(1), {}, data):
                        return eval(m.group(2), {}, data)
                    else:
                        return True
                else:
                    raise ValueError(f"条件格式错误: {cond}")
        elif rule_type == "cross_rule":
            # 使用前置规则结果
            cond = rule["condition"]
            # 替换 prev_rule_RXXX_result 为实际结果
            pattern = r"prev_rule_(R\d+)_result"
            matches = re.findall(pattern, cond)
            local_env = {}
            for rid in matches:
                local_env[f"prev_rule_{rid}_result"] = self.rule_results.get(rid, False)
            return eval(cond, {}, local_env)
        elif rule_type == "external":
            func_name = rule.get("external_rule")
            params = rule.get("params", [])
            func = self.external_funcs.get(func_name)
            if not func:
                raise ValueError(f"未找到 external 函数: {func_name}")
            args = [data.get(p) for p in params]
            return func(*args)
        else:
            raise ValueError(f"未知规则类型: {rule_type}")

    def register_external_func(self, func_name, func):
        """注册外部函数"""
        self.external_funcs[func_name] = func
