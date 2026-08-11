# tests/db/models/test_deployments.py

"""模型部署表测试

验证模型部署表的字段、索引、检查约束和字段注释。

核心功能：
  - test_deployment_table_and_columns:
    验证表名和字段集合
  - test_deployment_indexes:
    验证索引集合
  - test_deployment_check_constraints:
    验证检查约束集合
  - test_deployment_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.deployments import Deployment


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Deployment.__table__
)


def test_deployment_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "deployments"
    assert set(TABLE.columns.keys()) == {
        "deployment_id",
        "model_id",
        "version_id",
        "framework",
        "environment",
        "status",
        "rollout_type",
        "role",
        "effective_from",
        "effective_to",
        "config",
        "description",
        "deployed_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
        "id",
        "created_at",
        "updated_at",
    }


def test_deployment_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_deployments_effective_time",
        "idx_deployments_deleted_at",
        "idx_deployments_framework",
        "idx_deployments_model_id",
        "idx_deployments_model_id_environment_status",
        "idx_deployments_model_id_version_id",
        "uk_deployments_deployment_id",
    }


def test_deployment_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_deployments_config_object",
        "ck_deployments_effective_time_valid",
        "ck_deployments_environment_valid",
        "ck_deployments_role_valid",
        "ck_deployments_rollout_type_valid",
        "ck_deployments_shadow_role_consistent",
        "ck_deployments_status_valid",
    }


def test_deployment_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
