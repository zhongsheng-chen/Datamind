"""模型版本表测试.

验证模型版本表的字段、索引、检查约束和字段注释。

核心功能：
  - test_version_table_and_columns:
    验证表名和字段集合
  - test_version_indexes:
    验证索引集合
  - test_version_check_constraints:
    验证检查约束集合
  - test_version_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.versions import Version


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Version.__table__
)


def test_version_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "versions"
    assert set(TABLE.columns.keys()) == {
        "version_id",
        "model_id",
        "version",
        "framework",
        "status",
        "current_artifact_id",
        "artifact_revision",
        "artifact_sha256",
        "artifact_digest",
        "bento_tag",
        "model_path",
        "model_key",
        "params",
        "metrics",
        "description",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_id",
        "deletion_reason",
        "restored_at",
        "restored_by",
        "archived_at",
        "archived_by",
        "id",
        "created_at",
        "updated_at",
    }


def test_version_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_versions_created_at",
        "idx_versions_framework",
        "idx_versions_model_id",
        "idx_versions_status",
        "uk_versions_model_id_version",
        "uk_versions_version_id",
    }


def test_version_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_versions_artifact_revision_positive",
        "ck_versions_framework_valid",
        "ck_versions_metrics_object",
        "ck_versions_params_object",
        "ck_versions_status_valid",
    }


def test_version_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
