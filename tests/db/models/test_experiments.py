"""实验表测试

验证实验表的字段、索引、检查约束和字段注释。

核心功能：
  - test_experiment_table_and_columns:
    验证表名和字段集合
  - test_experiment_indexes:
    验证索引集合
  - test_experiment_check_constraints:
    验证检查约束集合
  - test_experiment_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.experiments import Experiment


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Experiment.__table__
)


def test_experiment_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "experiments"
    assert set(TABLE.columns.keys()) == {
        "experiment_id",
        "model_id",
        "environment",
        "name",
        "description",
        "status",
        "config",
        "effective_from",
        "effective_to",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_id",
        "deletion_reason",
        "id",
        "created_at",
        "updated_at",
    }


def test_experiment_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_experiments_created_at",
        "idx_experiments_deleted_at",
        "idx_experiments_effective_time",
        "idx_experiments_environment",
        "idx_experiments_model_environment_effective_time",
        "idx_experiments_model_environment_status",
        "idx_experiments_model_id",
        "idx_experiments_model_id_status",
        "idx_experiments_status",
        "uk_experiments_experiment_id",
        "uk_experiments_running_model_environment",
    }


def test_experiment_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_experiments_config_valid",
        "ck_experiments_effective_time_valid",
        "ck_experiments_environment_valid",
        "ck_experiments_status_valid",
    }


def test_experiment_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
