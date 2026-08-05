# tests/db/models/test_outbox.py

"""控制台事件表测试

验证控制台事件表的字段、索引、检查约束和字段注释。

核心功能：
  - test_outbox_table_and_columns: 验证表名和字段集合
  - test_outbox_indexes: 验证索引集合
  - test_outbox_check_constraints: 验证检查约束集合
  - test_outbox_column_comments: 验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.outbox import OutboxEvent


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    OutboxEvent.__table__
)


def test_outbox_table_and_columns() -> None:
    """验证表名和字段集合"""
    assert TABLE.name == "outbox"
    assert set(TABLE.columns.keys()) == {
        "event_id",
        "topic",
        "resource_id",
        "action",
        "schema_version",
        "occurred_at",
    }


def test_outbox_indexes() -> None:
    """验证索引集合"""
    assert {
        index.name
        for index in TABLE.indexes
    } == {
        "idx_outbox_occurred_at",
        "idx_outbox_topic_event_id",
    }


def test_outbox_check_constraints() -> None:
    """验证检查约束集合"""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(
            constraint,
            CheckConstraint,
        )
    } == {
        "ck_outbox_action_valid",
        "ck_outbox_schema_version_positive",
        "ck_outbox_topic_valid",
    }


def test_outbox_column_comments() -> None:
    """验证字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
