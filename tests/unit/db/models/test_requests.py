"""评分请求表测试.

验证评分请求表的字段、索引、检查约束和字段注释。

核心功能：
  - test_request_table_and_columns:
    验证表名和字段集合
  - test_request_indexes:
    验证索引集合
  - test_request_check_constraints:
    验证检查约束集合
  - test_request_column_comments:
    验证字段注释
"""

from sqlalchemy import (
    CheckConstraint,
    Table,
)

from datamind.db.models.requests import Request


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表."""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Request.__table__
)


def test_request_table_and_columns() -> None:
    """测试表名和字段集合."""
    assert TABLE.name == "requests"
    assert set(TABLE.columns.keys()) == {
        "request_id",
        "latest_decision_id",
        "batch_id",
        "batch_index",
        "model_id",
        "model_name",
        "payload",
        "response",
        "source",
        "status",
        "error",
        "latency_ms",
        "user",
        "ip",
        "id",
        "created_at",
        "updated_at",
    }


def test_request_allows_unresolved_model() -> None:
    """测试请求可在模型解析前持久化."""
    assert TABLE.columns["model_id"].nullable is True
    assert TABLE.columns["model_name"].nullable is True


def test_request_indexes() -> None:
    """测试索引集合."""
    assert {index.name for index in TABLE.indexes} == {
        "idx_requests_created_at",
        "idx_requests_batch_id",
        "idx_requests_model_id",
        "idx_requests_model_name",
        "idx_requests_source",
        "idx_requests_status",
        "idx_requests_user",
        "uk_requests_request_id",
        "uk_requests_batch_position",
    }


def test_request_check_constraints() -> None:
    """测试检查约束集合."""
    assert {
        constraint.name
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_requests_latency_ms_non_negative",
        "ck_requests_batch_fields_consistent",
        "ck_requests_batch_index_non_negative",
        "ck_requests_payload_object",
        "ck_requests_response_object",
        "ck_requests_status_valid",
    }


def test_request_column_comments() -> None:
    """测试字段注释."""
    for column in TABLE.columns.values():
        assert column.comment, column.name
