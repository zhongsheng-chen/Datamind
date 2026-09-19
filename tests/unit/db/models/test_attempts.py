"""批次执行尝试表测试

验证批次执行尝试表的字段、索引、检查约束和字段注释。

核心功能：
  - test_attempt_table_and_columns:
    验证表名和字段集合
  - test_attempt_indexes:
    验证索引集合
  - test_attempt_check_constraints:
    验证检查约束集合
  - test_attempt_column_comments:
    验证字段注释
"""

from sqlalchemy import CheckConstraint, Table

from datamind.db.models.attempts import Attempt


def get_model_table(value: object) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(Attempt.__table__)


def test_attempt_table_and_columns() -> None:
    """测试表名和字段集合"""
    assert TABLE.name == "attempts"
    assert set(TABLE.columns.keys()) == {
        "attempt_id",
        "batch_id",
        "task_id",
        "attempt_number",
        "status",
        "worker_id",
        "error",
        "retry_scheduled_at",
        "queued_at",
        "started_at",
        "finished_at",
        "id",
        "created_at",
        "updated_at",
    }


def test_attempt_indexes() -> None:
    """测试索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "uk_attempts_attempt_id",
        "uk_attempts_batch_number",
        "idx_attempts_task_id",
        "idx_attempts_status_created_at",
    }


def test_attempt_check_constraints() -> None:
    """测试检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_attempts_attempt_number_positive",
        "ck_attempts_status_valid",
        "ck_attempts_finished_status_valid",
    }


def test_attempt_column_comments() -> None:
    """测试字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
