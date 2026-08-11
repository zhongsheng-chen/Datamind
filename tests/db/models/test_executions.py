# tests/db/models/test_executions.py

"""模型执行表测试

验证模型执行表的字段、索引、检查约束、逻辑关联和字段注释。

核心功能：
  - test_execution_table_and_columns:
    验证表名和字段集合
  - test_execution_indexes:
    验证查询索引和唯一约束索引
  - test_execution_check_constraints:
    验证执行类型、状态和结果字段约束
  - test_execution_uses_logical_decision_reference:
    验证决策关联不使用数据库外键
  - test_execution_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.executions import Execution


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Execution.__table__
)


def test_execution_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "executions"
    assert set(TABLE.columns.keys()) == {
        "execution_id",
        "decision_id",
        "execution_type",
        "status",
        "model_id",
        "version_id",
        "deployment_id",
        "routing_id",
        "prediction",
        "probability",
        "score",
        "latency_ms",
        "error_type",
        "error",
        "context",
        "started_at",
        "finished_at",
        "id",
        "created_at",
        "updated_at",
    }


def test_execution_indexes() -> None:
    """验证查询索引和唯一约束索引"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_executions_created_at",
        "idx_executions_decision_id",
        "idx_executions_deployment_id",
        "idx_executions_model_id",
        "idx_executions_status",
        "idx_executions_type_status",
        "uk_executions_decision_deployment",
        "uk_executions_execution_id",
        "uk_executions_primary_decision",
    }

    unique_indexes = {
        index.name
        for index in TABLE.indexes
        if index.unique
    }
    assert unique_indexes == {
        "uk_executions_decision_deployment",
        "uk_executions_execution_id",
        "uk_executions_primary_decision",
    }


def test_execution_check_constraints() -> None:
    """验证执行类型、状态和结果字段约束"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_executions_context_object",
        "ck_executions_execution_type_valid",
        "ck_executions_latency_ms_non_negative",
        "ck_executions_prediction_object",
        "ck_executions_probability_range",
        "ck_executions_status_valid",
        "ck_executions_unfinished_status_valid",
    }


def test_execution_uses_logical_decision_reference() -> None:
    """验证决策关联不使用数据库外键"""
    assert not TABLE.foreign_key_constraints
    assert not TABLE.columns["decision_id"].foreign_keys


def test_execution_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
