"""批次执行分片表测试

验证批次执行分片表的字段、索引、检查约束和字段注释。

核心功能：
  - test_shard_table_and_columns:
    验证表名和字段集合
  - test_shard_indexes_and_constraints:
    验证索引和检查约束集合
  - test_shard_column_comments:
    验证字段注释
"""

from sqlalchemy import CheckConstraint, Table

from datamind.db.models.shards import Shard


def get_model_table(value: object) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(Shard.__table__)


def test_shard_table_and_columns() -> None:
    """测试表名和字段集合"""
    assert TABLE.name == "shards"
    assert set(TABLE.columns.keys()) == {
        "shard_id", "attempt_id", "batch_id", "task_id",
        "start_index", "end_index", "status", "worker_id", "error",
        "queued_at", "started_at", "finished_at",
        "id", "created_at", "updated_at",
    }


def test_shard_indexes_and_constraints() -> None:
    """测试索引和检查约束集合"""
    assert {index.name for index in TABLE.indexes} == {
        "uk_shards_shard_id",
        "uk_shards_range",
        "idx_shards_attempt_id",
        "idx_shards_task_id",
    }
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"ck_shards_range_valid", "ck_shards_status_valid"}


def test_shard_column_comments() -> None:
    """测试字段注释"""
    for column in TABLE.columns.values():
        assert column.comment, column.name
