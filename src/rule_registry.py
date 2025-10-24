#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rule_registry.py
规则注册与生命周期管理中心，支持冲突检查和热更新
"""

import os
import hashlib
import yaml
from datetime import datetime, date
from sqlalchemy import text
from src.config_parser import config
from src.setup import setup_logger
from src.db_engine import postgres_engine

logger = setup_logger()


class RuleRegistry:
    def __init__(self, rules_dir="rules", db_engine=None):
        self.rules_dir = rules_dir
        self.db_engine = db_engine or postgres_engine()

    def _get_file_hash(self, file_path):
        """计算文件 SHA256"""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _generate_rule_id(self):
        """生成规则编号 R0000XXXX 格式"""
        with self.db_engine.connect() as conn:
            result = conn.execute(text("SELECT nextval('rule_id_seq')")).scalar()
        return f"R{result:08d}"

    def _check_rule_conflict(self, business_name, stage, rule_name, category, group):
        """检查规则冲突"""
        with self.db_engine.connect() as conn:
            sql = """
                SELECT rule_id FROM rule_registry
                WHERE business_name=:business_name AND stage=:stage
                  AND rule_name=:rule_name AND rule_category=:category
                  AND rule_group=:group
            """
            result = conn.execute(text(sql), {
                "business_name": business_name,
                "stage": stage,
                "rule_name": rule_name,
                "category": category,
                "group": group
            }).fetchall()

            if len(result) > 1:
                logger.warning(
                    f"[规则冲突] 业务: {business_name}, 阶段: {stage}, "
                    f"规则名: {rule_name}, 类别: {category}, 分组: {group} "
                    f"存在 {len(result)} 条规则 ID: {[r['rule_id'] for r in result]}"
                )
                return True
        return False

    def register_rule(self, business_name, stage, rule_file):
        """注册单个规则文件，支持热更新"""
        rule_path = os.path.join(self.rules_dir, rule_file)
        if not os.path.exists(rule_path):
            logger.error(f"规则文件不存在: {rule_path}")
            return

        file_hash = self._get_file_hash(rule_path)
        with open(rule_path, "r", encoding="utf-8") as f:
            rule_data = yaml.safe_load(f)

        with self.db_engine.connect() as conn:
            for category, groups in rule_data.get("categories", {}).items():
                for group, rules in groups.items():
                    for rule in rules:
                        rule_name = rule.get("name", rule_file)
                        # 冲突检查
                        self._check_rule_conflict(business_name, stage, rule_name, category, group)

                        # 查询是否已存在
                        sql_check = """
                            SELECT rule_id, hash FROM rule_registry
                            WHERE business_name=:business_name AND rule_name=:rule_name
                              AND stage=:stage AND rule_category=:category AND rule_group=:group
                        """
                        existing = conn.execute(text(sql_check), {
                            "business_name": business_name,
                            "rule_name": rule_name,
                            "stage": stage,
                            "category": category,
                            "group": group
                        }).first()

                        if existing:
                            # 热更新：文件哈希变化则更新
                            if existing["hash"] != file_hash:
                                sql_update = """
                                    UPDATE rule_registry
                                    SET hash=:hash, rule_desc=:desc, updated_at=:updated_at, version=:version
                                    WHERE rule_id=:rule_id
                                """
                                conn.execute(text(sql_update), {
                                    "hash": file_hash,
                                    "desc": rule.get("description", ""),
                                    "updated_at": datetime.now(),
                                    "version": rule.get("version", "v1"),
                                    "rule_id": existing["rule_id"]
                                })
                                logger.info(f"[热更新] 规则更新: {existing['rule_id']}")
                        else:
                            # 新增规则
                            rule_id = self._generate_rule_id()
                            sql_insert = """
                                INSERT INTO rule_registry
                                (rule_id, business_name, rule_name, rule_path, rule_category, rule_group,
                                 stage, version, status, created_at, updated_at, hash, rule_desc,
                                 effective_date, expiration_date)
                                VALUES
                                (:rule_id, :business_name, :rule_name, :rule_path, :rule_category, :rule_group,
                                 :stage, :version, 'active', :created_at, :updated_at, :hash, :rule_desc,
                                 :effective_date, :expiration_date)
                            """
                            conn.execute(text(sql_insert), {
                                "rule_id": rule_id,
                                "business_name": business_name,
                                "rule_name": rule_name,
                                "rule_path": rule_path,
                                "rule_category": category,
                                "rule_group": group,
                                "stage": stage,
                                "version": rule.get("version", "v1"),
                                "created_at": datetime.now(),
                                "updated_at": datetime.now(),
                                "hash": file_hash,
                                "rule_desc": rule.get("description", ""),
                                "effective_date": rule.get("effective_date", date.today()),
                                "expiration_date": rule.get("expiration_date", date(9999, 12, 31))
                            })
                            logger.info(f"[注册] 规则新增: {rule_id}")
            conn.commit()

    def deactivate_rule(self, rule_id):
        """失效规则"""
        with self.db_engine.connect() as conn:
            conn.execute(
                text("UPDATE rule_registry SET status='inactive', updated_at=:updated_at WHERE rule_id=:rule_id"),
                {"rule_id": rule_id, "updated_at": datetime.now()}
            )
            conn.commit()
        logger.info(f"规则失效: {rule_id}")

    def enable_rule(self, rule_id):
        """激活规则"""
        with self.db_engine.connect() as conn:
            conn.execute(
                text("UPDATE rule_registry SET status='active', updated_at=:updated_at WHERE rule_id=:rule_id"),
                {"rule_id": rule_id, "updated_at": datetime.now()}
            )
            conn.commit()
        logger.info(f"规则激活: {rule_id}")

    def delete_rule(self, rule_id):
        """彻底删除规则"""
        with self.db_engine.connect() as conn:
            conn.execute(text("DELETE FROM rule_registry WHERE rule_id=:rule_id"), {"rule_id": rule_id})
            conn.commit()
        logger.info(f"规则删除: {rule_id}")

    def list_rules(self, business_name=None, stage=None, status="active"):
        """查询规则"""
        with self.db_engine.connect() as conn:
            query = "SELECT * FROM rule_registry WHERE status=:status"
            params = {"status": status}
            if business_name:
                query += " AND business_name=:business_name"
                params["business_name"] = business_name
            if stage:
                query += " AND stage=:stage"
                params["stage"] = stage
            result = conn.execute(text(query), params).fetchall()
            return [dict(r) for r in result]

    def register_all_rules(self):
        """扫描 rules/ 目录，批量注册所有规则文件"""
        for rule_file in os.listdir(self.rules_dir):
            if rule_file.endswith(".yaml") or rule_file.endswith(".yml"):
                # 根据文件名判断业务和阶段
                # 例如 personal_loan_rule_20250930.yaml -> personal_loan
                if "personal_loan" in rule_file:
                    business_name = "PersonalLoan"
                    stage = "Underwriting"  # 或根据文件内容配置
                elif "auto_loan" in rule_file:
                    business_name = "AutoLoan"
                    stage = "Underwriting"
                else:
                    business_name = "General"
                    stage = "Underwriting"

                self.register_rule(business_name, stage, rule_file)

