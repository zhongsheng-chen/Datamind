"""模型元数据表测试

验证模型元数据表的字段、索引、检查约束和字段注释。

核心功能：
  - test_metadata_table_and_columns:
    验证表名和字段集合
  - test_metadata_indexes:
    验证索引集合
  - test_metadata_check_constraints:
    验证检查约束集合
  - test_metadata_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.metadata import Metadata


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Metadata.__table__
)


def test_metadata_table_and_columns() -> None:
    """测试表名和字段集合"""
    assert TABLE.name == "metadata"
    assert set(TABLE.columns.keys()) == {
        "model_id",
        "name",
        "display_name",
        "model_type",
        "task_type",
        "framework",
        "description",
        "status",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_id",
        "deletion_reason",
        "restored_at",
        "restored_by",
        "archived_at",
        "archived_by",
        "id",
        "created_at",
        "updated_at",
    }


def test_metadata_indexes() -> None:
    """测试索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_metadata_created_at",
        "idx_metadata_framework",
        "idx_metadata_model_type",
        "idx_metadata_status",
        "idx_metadata_task_type",
        "uk_metadata_model_id",
        "uk_metadata_name",
    }


def test_metadata_check_constraints() -> None:
    """测试检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_metadata_framework_valid",
        "ck_metadata_model_type_valid",
        "ck_metadata_status_valid",
        "ck_metadata_task_type_valid",
    }


def test_metadata_column_comments() -> None:
    """测试字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
