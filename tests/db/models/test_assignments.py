"""实验分配表测试

验证实验分配表的字段、索引、检查约束和字段注释。

核心功能：
  - test_assignment_table_and_columns:
    验证表名和字段集合
  - test_assignment_indexes:
    验证索引集合
  - test_assignment_check_constraints:
    验证检查约束集合
  - test_assignment_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.assignments import Assignment


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Assignment.__table__
)


def test_assignment_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "assignments"
    assert set(TABLE.columns.keys()) == {
        "assignment_id",
        "experiment_id",
        "variant_id",
        "subject_key",
        "subject_type",
        "strategy",
        "bucket",
        "weight",
        "context",
        "assigned_at",
        "id",
        "created_at",
        "updated_at",
    }


def test_assignment_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_assignments_assigned_at",
        "idx_assignments_created_at",
        "idx_assignments_experiment_id",
        "idx_assignments_subject_key",
        "idx_assignments_variant_id",
        "uk_assignments_assignment_id",
        "uk_assignments_experiment_subject",
    }


def test_assignment_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_assignments_context_object",
        "ck_assignments_strategy_valid",
        "ck_assignments_weight_range",
    }


def test_assignment_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
