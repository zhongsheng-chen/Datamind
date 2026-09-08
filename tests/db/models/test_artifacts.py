"""模型制品表测试

验证模型制品表的字段、索引、检查约束和字段注释。

核心功能：
  - test_artifact_table_and_columns: 验证表名和字段集合
  - test_artifact_indexes: 验证索引集合
  - test_artifact_check_constraints: 验证检查约束集合
  - test_artifact_column_comments: 验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.artifacts import Artifact


def get_model_table(value: object) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(Artifact.__table__)


def test_artifact_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "artifacts"
    assert set(TABLE.columns.keys()) == {
        "artifact_id",
        "version_id",
        "revision",
        "sha256",
        "digest",
        "source_path",
        "model_key",
        "bento_tag",
        "status",
        "created_by",
        "retired_at",
        "retired_by",
        "purge_requested_at",
        "purge_requested_by",
        "purge_reason",
        "purged_at",
        "purged_by",
        "purge_attempts",
        "purge_error",
        "id",
        "created_at",
        "updated_at",
    }


def test_artifact_indexes() -> None:
    """验证索引集合"""
    assert {index.name for index in TABLE.indexes} == {
        "idx_artifacts_status",
        "idx_artifacts_version_id",
        "uk_artifacts_active_version",
        "uk_artifacts_artifact_id",
        "uk_artifacts_bento_tag",
        "uk_artifacts_model_key",
        "uk_artifacts_version_revision",
    }


def test_artifact_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_artifacts_purge_attempts_non_negative",
        "ck_artifacts_revision_positive",
        "ck_artifacts_status_valid",
    }


def test_artifact_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
