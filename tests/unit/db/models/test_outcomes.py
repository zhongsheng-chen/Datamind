"""业务结果表测试.

验证业务结果表的字段、索引、检查约束和字段注释。

核心功能：
  - test_outcome_table_and_columns:
    验证表名和字段集合
  - test_outcome_indexes:
    验证索引集合
  - test_outcome_check_constraints:
    验证检查约束集合
  - test_outcome_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.outcomes import Outcome


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Outcome.__table__
)


def test_outcome_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "outcomes"
    assert set(TABLE.columns.keys()) == {
        "outcome_id",
        "experiment_id",
        "variant_id",
        "assignment_id",
        "decision_id",
        "request_id",
        "subject_key",
        "subject_type",
        "approved",
        "converted",
        "defaulted",
        "overdue_days",
        "amount",
        "label",
        "context",
        "outcome_time",
        "id",
        "created_at",
        "updated_at",
    }


def test_outcome_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_outcomes_assignment_id",
        "idx_outcomes_created_at",
        "idx_outcomes_decision_id",
        "idx_outcomes_experiment_id",
        "idx_outcomes_outcome_time",
        "idx_outcomes_request_id",
        "idx_outcomes_subject_key",
        "idx_outcomes_variant_id",
        "uk_outcomes_outcome_id",
    }


def test_outcome_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_outcomes_amount_non_negative",
        "ck_outcomes_context_object",
        "ck_outcomes_overdue_days_non_negative",
    }


def test_outcome_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
