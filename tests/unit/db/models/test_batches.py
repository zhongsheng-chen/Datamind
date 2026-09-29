"""预测批次表测试.

验证预测批次表的字段、索引、检查约束和字段注释。

核心功能：
  - test_batch_table_and_columns:
    验证表名和字段集合
  - test_batch_indexes:
    验证索引集合
  - test_batch_check_constraints:
    验证检查约束集合
  - test_batch_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.batches import Batch


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Batch.__table__
)


def test_batch_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "batches"
    assert set(TABLE.columns.keys()) == {
        "batch_id",
        "task_id",
        "model_id",
        "model_name",
        "deployment_id",
        "environment",
        "status",
        "payload",
        "result",
        "error",
        "total_count",
        "completed_count",
        "succeeded_count",
        "failed_count",
        "attempt_count",
        "cancel_requested_at",
        "started_at",
        "finished_at",
        "source",
        "user",
        "ip",
        "id",
        "created_at",
        "updated_at",
    }


def test_batch_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "uk_batches_batch_id",
        "uk_batches_task_id",
        "idx_batches_status_created_at",
    }


def test_batch_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_batches_status_valid",
        "ck_batches_total_count_positive",
        "ck_batches_counts_non_negative",
        "ck_batches_counts_within_total",
        "ck_batches_attempt_count_non_negative",
    }
    status_constraint = next(
        constraint
        for constraint in TABLE.constraints
        if constraint.name == "ck_batches_status_valid"
    )
    assert isinstance(
        status_constraint,
        CheckConstraint,
    )
    assert "'retrying'" in str(status_constraint.sqltext)


def test_batch_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
    assert "retrying" in str(TABLE.columns.status.comment)
