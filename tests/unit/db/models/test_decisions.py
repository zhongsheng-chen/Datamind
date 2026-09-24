"""评分决策表测试.

验证评分决策表的字段、索引、检查约束和字段注释。

核心功能：
  - test_decision_table_and_columns:
    验证表名和字段集合
  - test_decision_indexes:
    验证索引集合
  - test_decision_check_constraints:
    验证检查约束集合
  - test_decision_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.decisions import Decision


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Decision.__table__
)


def test_decision_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "decisions"
    assert set(TABLE.columns.keys()) == {
        "decision_id",
        "request_id",
        "model_id",
        "version_id",
        "deployment_id",
        "experiment_id",
        "variant_id",
        "assignment_id",
        "subject_key",
        "subject_type",
        "source",
        "strategy",
        "bucket",
        "group",
        "weight",
        "decision",
        "context",
        "decided_at",
        "id",
        "created_at",
        "updated_at",
    }


def test_decision_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_decisions_assignment_id",
        "idx_decisions_created_at",
        "idx_decisions_deployment_id",
        "idx_decisions_experiment_id",
        "idx_decisions_model_id",
        "idx_decisions_request_latest",
        "idx_decisions_source",
        "idx_decisions_subject_key",
        "idx_decisions_variant_id",
        "idx_decisions_version_id",
        "uk_decisions_decision_id",
    }

    request_index = next(
        index
        for index in TABLE.indexes
        if index.name == "idx_decisions_request_latest"
    )
    assert request_index.unique is False


def test_decision_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_decisions_context_object",
        "ck_decisions_source_valid",
        "ck_decisions_strategy_valid",
        "ck_decisions_weight_range",
    }


def test_decision_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
