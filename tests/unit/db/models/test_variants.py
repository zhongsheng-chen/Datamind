"""实验分组表测试.

验证实验分组表的字段、索引、检查约束和字段注释。

核心功能：
  - test_variant_table_and_columns:
    验证表名和字段集合
  - test_variant_indexes:
    验证索引集合
  - test_variant_deployment_unique_index:
    验证实验和部署组合唯一索引
  - test_variant_check_constraints:
    验证检查约束集合
  - test_variant_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Index,
    Table,
)

from datamind.db.models.variants import Variant


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Variant.__table__
)


def get_index_column_names(
        index: Index,
) -> list[str]:
    """获取索引字段名称."""
    column_names: list[str] = []

    for expression in index.expressions:
        name = getattr(
            expression,
            "name",
            None,
        )

        assert isinstance(
            name,
            str,
        )

        column_names.append(
            name
        )

    return column_names


def test_variant_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "variants"
    assert set(TABLE.columns.keys()) == {
        "variant_id",
        "experiment_id",
        "name",
        "deployment_id",
        "weight",
        "is_control",
        "status",
        "config",
        "description",
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


def test_variant_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_variants_created_at",
        "idx_variants_deleted_at",
        "idx_variants_deployment_id",
        "idx_variants_experiment_id",
        "idx_variants_experiment_status",
        "idx_variants_status",
        "uk_variants_active_control",
        "uk_variants_experiment_deployment",
        "uk_variants_experiment_name",
        "uk_variants_variant_id",
    }


def test_variant_deployment_unique_index() -> None:
    """测试实验和部署组合唯一索引."""
    index = next(
        item
        for item in TABLE.indexes
        if item.name == "uk_variants_experiment_deployment"
    )

    assert index.unique
    assert get_index_column_names(
        index
    ) == [
        "experiment_id",
        "deployment_id",
    ]


def test_variant_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_variants_config_object",
        "ck_variants_status_valid",
        "ck_variants_weight_range",
    }


def test_variant_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
