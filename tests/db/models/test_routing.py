# tests/db/models/test_routing.py

"""路由规则表测试

验证路由规则表的字段、索引、检查约束和字段注释。

核心功能：
  - test_routing_table_and_columns:
    验证表名和字段集合
  - test_routing_indexes:
    验证索引集合
  - test_routing_check_constraints:
    验证检查约束集合
  - test_routing_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.routing import Routing


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Routing.__table__
)


def test_routing_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "routing"
    assert set(TABLE.columns.keys()) == {
        "routing_id",
        "deployment_id",
        "rollout_type",
        "rollout_group",
        "environment",
        "enabled",
        "traffic_ratio",
        "rules",
        "description",
        "created_by",
        "updated_by",
        "id",
        "created_at",
        "updated_at",
    }


def test_routing_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_routing_deployment_id",
        "idx_routing_environment_enabled",
        "idx_routing_rollout_group_enabled",
        "idx_routing_rollout_type_enabled",
        "uk_routing_routing_id",
    }


def test_routing_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_routing_environment_valid",
        "ck_routing_rollout_group_valid",
        "ck_routing_rollout_type_valid",
        "ck_routing_rules_object",
        "ck_routing_traffic_ratio_range",
    }


def test_routing_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
