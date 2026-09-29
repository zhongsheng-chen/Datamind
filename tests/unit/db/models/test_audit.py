"""审计日志表测试.

验证审计日志表的字段、索引、检查约束和字段注释。

核心功能：
  - test_audit_table_and_columns:
    验证表名和字段集合
  - test_audit_indexes:
    验证索引集合
  - test_audit_check_constraints:
    验证检查约束集合
  - test_audit_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.audit import Audit


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Audit.__table__
)


def test_audit_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "audit"
    assert set(TABLE.columns.keys()) == {
        "audit_id",
        "action",
        "resource",
        "operation",
        "target_type",
        "target_id",
        "source",
        "trace_id",
        "request_id",
        "user",
        "ip",
        "hostname",
        "status",
        "error",
        "before",
        "after",
        "context",
        "occurred_at",
        "id",
        "created_at",
        "updated_at",
    }


def test_audit_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_audit_failed_occurred_at",
        "idx_audit_occurred_at",
        "idx_audit_request_id_occurred_at",
        "idx_audit_source_occurred_at",
        "idx_audit_target_id_occurred_at",
        "idx_audit_target_type_occurred_at",
        "idx_audit_trace_id_occurred_at",
        "idx_audit_user_occurred_at",
        "uk_audit_audit_id",
    }


def test_audit_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_audit_context_object",
        "ck_audit_source_valid",
        "ck_audit_status_valid",
    }


def test_audit_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name


def test_audit_optional_json_uses_sql_null() -> None:
    """测试可选 JSON 字段将 Python None 写为 SQL NULL."""
    for column_name in (
            "before",
            "after",
            "context",
    ):
        assert TABLE.columns[
            column_name
        ].type.none_as_null is True
