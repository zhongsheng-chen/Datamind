"""运行控制表测试

验证运行控制表的字段、索引、检查约束和字段注释。

核心功能：
  - test_control_table_and_columns:
    验证表名和字段集合
  - test_control_indexes:
    验证索引集合
  - test_control_check_constraints:
    验证检查约束集合
  - test_control_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.controls import Control


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Control.__table__
)


def test_control_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "controls"
    assert set(TABLE.columns.keys()) == {
        "control_id",
        "deployment_id",
        "environment",
        "desired_status",
        "generation",
        "created_by",
        "updated_by",
        "id",
        "created_at",
        "updated_at",
    }


def test_control_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_controls_desired_status",
        "idx_controls_environment",
        "idx_controls_environment_desired_status",
        "idx_controls_updated_at",
        "uk_controls_control_id",
        "uk_controls_deployment_id",
    }


def test_control_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_controls_desired_status_valid",
        "ck_controls_environment_valid",
        "ck_controls_generation_positive",
    }


def test_control_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
