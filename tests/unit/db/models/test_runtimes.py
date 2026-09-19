"""模型运行表测试

验证模型运行表的字段、索引、检查约束和字段注释。

核心功能：
  - test_runtime_table_and_columns:
    验证表名和字段集合
  - test_runtime_indexes:
    验证索引集合
  - test_runtime_check_constraints:
    验证检查约束集合
  - test_runtime_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.runtimes import Runtime


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Runtime.__table__
)


def test_runtime_table_and_columns() -> None:
    """测试表名和字段集合"""
    assert TABLE.name == "runtimes"
    assert set(TABLE.columns.keys()) == {
        "runtime_id",
        "deployment_id",
        "model_id",
        "version_id",
        "framework",
        "status",
        "worker_id",
        "loaded_at",
        "unloaded_at",
        "started_by",
        "stopped_by",
        "last_heartbeat_at",
        "applied_generation",
        "error",
        "context",
        "id",
        "created_at",
        "updated_at",
    }


def test_runtime_indexes() -> None:
    """测试索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_runtimes_framework",
        "idx_runtimes_last_heartbeat_at",
        "idx_runtimes_loaded_at",
        "idx_runtimes_model_id",
        "idx_runtimes_status",
        "idx_runtimes_version_id",
        "idx_runtimes_worker_id",
        "uk_runtimes_deployment_worker",
        "uk_runtimes_runtime_id",
    }


def test_runtime_check_constraints() -> None:
    """测试检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_runtimes_applied_generation_positive",
        "ck_runtimes_context_object",
        "ck_runtimes_framework_valid",
        "ck_runtimes_status_valid",
    }


def test_runtime_column_comments() -> None:
    """测试字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
