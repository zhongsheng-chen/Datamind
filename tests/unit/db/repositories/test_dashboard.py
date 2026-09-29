"""管理控制台查询仓储测试.

验证控制台页面记录总数、关键词与字段化查询和参数校验。

核心功能：
  - test_get_counts:
    验证查询指定页面记录总数
  - test_get_counts_rejects_unknown_section:
    验证拒绝未知页面
  - test_get_counts_returns_empty_without_sections:
    验证空页面集合
  - test_count_records:
    验证查询条件下的精确记录总数
  - test_get_request_metrics:
    验证 API 调用核心指标查询
  - test_get_request_trend:
    验证 API 调用趋势查询
  - test_get_model_request_stats:
    验证模型调用统计查询
  - test_get_experiment_labels:
    验证实验模型信息查询
  - test_get_variant_labels:
    验证分组实验和模型信息查询
  - test_get_batch_deployment_stats:
    验证批次实际命中部署统计查询
  - test_get_attempt_shard_details:
    验证执行尝试分片进度聚合查询
  - test_get_execution_details:
    验证模型执行关联信息查询
  - test_get_decision_executions:
    验证决策模型执行查询
  - test_get_variant_counts:
    验证实验分组数量查询
  - test_get_version_labels:
    验证版本模型名称查询
  - test_search_records:
    验证关键词查询和分页
  - test_search_records_supports_field_queries:
    验证字段化查询
  - test_decision_queries_support_experiment_id:
    验证决策列表及计数按实验筛选
  - test_search_records_supports_time_ranges:
    验证时间范围查询
  - test_search_records_rejects_unknown_search_field:
    验证拒绝未知查询字段
  - test_search_records_sorts_related_fields:
    验证关联字段排序
  - test_search_records_sorts_batch_requests_by_position:
    验证批次请求按照批次位置排序
  - test_search_records_filters_batch_attempts:
    验证按照批次筛选并排序执行尝试
  - test_search_records_supports_multiple_sort_fields:
    验证多字段优先级排序
  - test_search_variants:
    验证实验分组查询和排序
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import (
    Any,
    cast,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import (
    operators,
    visitors,
)

from datamind.db.models import Shard
from datamind.runtime.presence import RuntimePresence

from datamind.db.repositories.dashboard import DashboardRepository


def get_ilike_predicates(statement: Any) -> list[Any]:
    """返回查询中的所有 ILIKE 谓词."""
    predicates: list[Any] = []

    def collect_predicate(expression: Any) -> None:
        if expression.operator is operators.ilike_op:
            predicates.append(expression)

    visitors.traverse(
        statement,
        {},
        {
            "binary": collect_predicate,
        },
    )
    return predicates


def create_repository() -> tuple[DashboardRepository, AsyncMock]:
    """创建控制台统计仓储及会话替身."""
    result = MagicMock()
    result.mappings.return_value.one.return_value = {
        "models": 4,
        "audits": 33,
    }
    result.scalar_one.return_value = 33
    execute = AsyncMock(
        return_value=result
    )
    session_mock = MagicMock(
        spec=AsyncSession
    )
    session_mock.execute = execute
    session = cast(
        AsyncSession,
        cast(
            object,
            session_mock,
        ),
    )

    return DashboardRepository(session), execute


@pytest.mark.asyncio
async def test_get_counts() -> None:
    """测试使用单条语句查询指定页面记录总数."""
    repository, execute = create_repository()

    counts = await repository.get_counts([
        "models",
        "audits",
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert counts == {
        "models": 4,
        "audits": 33,
    }
    assert sql.count("SELECT count(*)") == 2
    assert "FROM metadata" in sql
    assert "FROM audit" in sql
    assert "metadata.deleted_at IS NULL" in sql


@pytest.mark.asyncio
async def test_get_counts_rejects_unknown_section() -> None:
    """测试拒绝未知控制台页面."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="不支持的控制台页面: unknown",
    ):
        await repository.get_counts([
            "unknown"
        ])

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_counts_returns_empty_without_sections() -> None:
    """测试空页面集合不查询数据库."""
    repository, execute = create_repository()

    counts = await repository.get_counts([])

    assert counts == {}
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_count_records() -> None:
    """测试查询指定条件下的精确记录总数."""
    repository, execute = create_repository()

    count = await repository.count_records(
        section="versions",
        query="score",
        model_id="mdl_test",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert count == 33
    assert "SELECT count(*)" in sql
    assert "versions.model_id = 'mdl_test'" in sql
    assert "ILIKE" in sql
    assert "score" in sql
    assert "versions.deleted_at IS NULL" in sql


@pytest.mark.asyncio
async def test_search_records() -> None:
    """测试模型页面使用关键词查询并分页."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="score",
        limit=11,
        offset=10,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM metadata" in sql
    assert "ILIKE" in sql
    assert "score" in sql
    assert "metadata.created_at ILIKE" not in sql
    assert "metadata.updated_at ILIKE" not in sql
    assert "LIMIT 11 OFFSET 10" in sql


@pytest.mark.asyncio
async def test_search_routings_supports_version_id() -> None:
    """测试路由关键词查询包含关联部署的版本 ID."""
    repository, execute = create_repository()

    await repository.search_records(
        section="routings",
        query="ver_64a1c9a48d9bf163",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "LEFT OUTER JOIN deployments" in sql
    assert "deployments.version_id ILIKE" in sql
    assert "ver" in sql
    assert "64a1c9a48d9bf163" in sql


@pytest.mark.asyncio
async def test_search_routings_supports_route_name() -> None:
    """测试路由关键词查询包含路由名称."""
    repository, execute = create_repository()

    await repository.search_records(
        section="routings",
        query="scorecard-route",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "routing.name ILIKE" in sql
    assert "scorecard" in sql
    assert "routing" in sql


@pytest.mark.asyncio
async def test_search_deleted_versions() -> None:
    """测试回收站仅查询已逻辑删除版本."""
    repository, execute = create_repository()

    await repository.search_records(
        section="versions",
        query="",
        model_id="mdl_test",
        limit=10,
        offset=0,
        only_deleted=True,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "versions.deleted_at IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_search_deleted_models() -> None:
    """测试模型回收站仅查询整体逻辑删除的模型."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="",
        limit=10,
        offset=0,
        only_deleted=True,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "metadata.deleted_at IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_search_runtimes_returns_current_instances() -> None:
    """测试运行实例分页只返回状态活动且心跳有效的实例."""
    repository, execute = create_repository()
    presence = RuntimePresence(
        stale_at=datetime(
            2026,
            8,
            26,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )

    await repository.search_records(
        section="runtimes",
        query="",
        limit=10,
        offset=0,
        presence=presence,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "runtimes.status IN ('starting', 'running', 'stopping')" in sql
    assert "coalesce(runtimes.last_heartbeat_at, runtimes.updated_at)" in sql
    assert "2026-08-26 18:00:00+00:00" in sql


@pytest.mark.asyncio
async def test_search_runtimes_sorts_by_stored_status() -> None:
    """测试运行实例按数据库中的运行状态排序."""
    repository, execute = create_repository()
    presence = RuntimePresence(
        stale_at=datetime(
            2026,
            8,
            26,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )

    await repository.search_records(
        section="runtimes",
        query="",
        limit=10,
        offset=0,
        sort_by="status",
        sort_order="asc",
        presence=presence,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ORDER BY runtimes.status ASC NULLS LAST" in sql


@pytest.mark.asyncio
async def test_search_runtimes_sorts_by_health_status() -> None:
    """测试运行实例按派生的健康状态排序."""
    repository, execute = create_repository()
    presence = RuntimePresence(
        stale_at=datetime(
            2026,
            8,
            26,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )

    await repository.search_records(
        section="runtimes",
        query="",
        limit=10,
        offset=0,
        sort_by="health_status",
        sort_order="asc",
        presence=presence,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "THEN 'unhealthy'" in sql
    assert "ELSE 'healthy' END ASC NULLS LAST" in sql


@pytest.mark.asyncio
async def test_search_records_supports_field_queries() -> None:
    """测试字段条件按字段匹配并使用 AND 组合."""
    repository, execute = create_repository()

    await repository.search_records(
        section="deployments",
        query='model:"credit score" status:active',
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "metadata.name ILIKE" in sql
    assert "credit score" in sql
    assert "deployments.status ILIKE" in sql
    assert "active" in sql
    assert "%active%" not in sql
    assert sql.count("ILIKE") == 2
    assert " AND " in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("count_only", [False, True])
@pytest.mark.parametrize("field", ["experiment_id", "experiment"])
async def test_decision_queries_support_experiment_id(
        count_only: bool,
        field: str,
) -> None:
    """测试决策列表和计数支持实验 ID 及其别名与策略组合查询."""
    repository, execute = create_repository()
    query = f"{field}:exp_test strategy:manual"

    if count_only:
        await repository.count_records(
            section="decisions",
            query=query,
        )
    else:
        await repository.search_records(
            section="decisions",
            query=query,
            limit=10,
            offset=0,
        )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
        )
    )
    parameters = statement.compile().params

    assert "decisions.experiment_id ILIKE" in sql
    assert "decisions.strategy ILIKE" in sql
    assert "manual" in parameters.values()
    assert any(
        isinstance(value, str)
        and value.replace("\\", "") == "exp_test"
        for value in parameters.values()
    )
    assert " AND " in sql


@pytest.mark.asyncio
async def test_search_records_supports_time_ranges() -> None:
    """测试日期范围包含结束日期并按本地时区转换."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="updated_at:2026-08-01..2026-08-18",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "metadata.updated_at >=" in sql
    assert "metadata.updated_at <" in sql
    assert "2026-07-31 16:00:00+00:00" in sql
    assert "2026-08-18 16:00:00+00:00" in sql


@pytest.mark.asyncio
async def test_search_records_supports_display_time_ranges() -> None:
    """测试时间范围兼容页面展示的日期时间格式."""
    repository, execute = create_repository()

    await repository.search_records(
        section="audits",
        query=(
            "occurred_at:2026/08/17 00:00:00"
            "..2026/08/18 23:59:59"
        ),
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "audit.occurred_at >=" in sql
    assert "audit.occurred_at <=" in sql
    assert "2026-08-16 16:00:00+00:00" in sql
    assert "2026-08-18 15:59:59+00:00" in sql


@pytest.mark.asyncio
async def test_search_records_supports_open_time_ranges() -> None:
    """测试时间范围支持省略起点或终点."""
    repository, execute = create_repository()

    await repository.search_records(
        section="requests",
        query="time:2026-08-18T09:30:00+08:00..",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "requests.created_at >=" in sql
    assert "2026-08-18 01:30:00+00:00" in sql
    assert "requests.created_at <" not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "section",
        "field",
        "expected_column",
    ),
    [
        (
            "models",
            "deleted_at",
            "metadata.deleted_at",
        ),
        (
            "models",
            "restored_at",
            "metadata.restored_at",
        ),
        (
            "models",
            "archived_at",
            "metadata.archived_at",
        ),
        (
            "versions",
            "deleted_at",
            "versions.deleted_at",
        ),
        (
            "versions",
            "restored_at",
            "versions.restored_at",
        ),
        (
            "versions",
            "archived_at",
            "versions.archived_at",
        ),
        (
            "requests",
            "updated_at",
            "requests.updated_at",
        ),
        (
            "decisions",
            "updated_at",
            "decisions.updated_at",
        ),
        (
            "executions",
            "updated_at",
            "executions.updated_at",
        ),
        (
            "audits",
            "updated_at",
            "audit.updated_at",
        ),
    ],
)
async def test_search_records_supports_lifecycle_times(
        section: str,
        field: str,
        expected_column: str,
) -> None:
    """测试控制台页面支持附加生命周期时间字段."""
    repository, execute = create_repository()

    await repository.search_records(
        section=section,
        query=f"{field}:2026-08-18",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert f"{expected_column} >=" in sql
    assert f"{expected_column} <" in sql


@pytest.mark.asyncio
async def test_search_records_rejects_invalid_time_range() -> None:
    """测试拒绝起止顺序错误的时间范围."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="起始时间不能晚于结束时间",
    ):
        await repository.search_records(
            section="audits",
            query="time:2026-08-19..2026-08-18",
            limit=10,
            offset=0,
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_records_combines_keyword_and_field_query() -> None:
    """测试普通关键词可以和字段条件组合."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="scorecard status:active",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "metadata.name ILIKE" in sql
    assert "scorecard" in sql
    assert "metadata.status ILIKE" in sql
    assert "active" in sql
    assert " AND " in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "classification",
        "task_type:classification",
    ],
)
async def test_search_requests_supports_task_type(
        query: str,
) -> None:
    """测试 API 调用记录支持按任务类型查询."""
    repository, execute = create_repository()

    await repository.search_records(
        section="requests",
        query=query,
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "LEFT OUTER JOIN metadata" in sql
    assert "metadata.task_type ILIKE" in sql
    assert "classification" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("count_only", [False, True])
async def test_request_queries_support_batch_index(
        count_only: bool,
) -> None:
    """测试 API 调用列表和计数支持按批次位置精确查询."""
    repository, execute = create_repository()

    if count_only:
        await repository.count_records(
            section="requests",
            query="batch_index:3",
        )
    else:
        await repository.search_records(
            section="requests",
            query="batch_index:3",
            limit=10,
            offset=0,
        )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "requests.batch_index = 3" in sql


@pytest.mark.asyncio
async def test_request_queries_reject_invalid_batch_index() -> None:
    """测试批次位置拒绝非整数查询值."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="查询字段 batch_index 只支持整数值",
    ):
        await repository.search_records(
            section="requests",
            query="batch_index:first",
            limit=10,
            offset=0,
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_queries_support_batch_index_range() -> None:
    """测试 API 调用列表支持按批次位置范围查询."""
    repository, execute = create_repository()

    await repository.search_records(
        section="requests",
        query="batch_id:bat_test batch_index:20..39",
        limit=20,
        offset=0,
        sort_by="batch_index",
        sort_order="asc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "requests.batch_index BETWEEN 20 AND 39" in sql


@pytest.mark.asyncio
async def test_search_records_rejects_unknown_search_field() -> None:
    """测试拒绝当前页面不支持的查询字段."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="不支持的查询字段: password_hash",
    ):
        await repository.search_records(
            section="models",
            query="password_hash:secret",
            limit=10,
            offset=0,
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_records_rejects_empty_field_value() -> None:
    """测试字段化查询拒绝空值."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="查询字段 status 缺少值",
    ):
        await repository.search_records(
            section="models",
            query="status:",
            limit=10,
            offset=0,
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_records_preserves_plain_query_punctuation() -> None:
    """测试普通关键词保留引号类标点并继续模糊匹配."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="O'Brien score",
        limit=10,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "O''Brien score" in sql


@pytest.mark.asyncio
async def test_search_records_filters_selected_identifiers() -> None:
    """测试查询记录可限定为用户选择的主键集合."""
    repository, execute = create_repository()

    await repository.search_records(
        section="models",
        query="",
        record_ids=(
            "mdl_first",
            "mdl_second",
        ),
        limit=100,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert (
        "metadata.model_id IN "
        "('mdl_first', 'mdl_second')"
    ) in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "section",
        "sort_by",
        "expected_sql",
    ),
    [
        (
            "deployments",
            "model_name",
            "metadata.name ASC NULLS LAST",
        ),
        (
            "versions",
            "model_name",
            "metadata.name ASC NULLS LAST",
        ),
        (
            "routings",
            "model_version",
            "versions.version ASC NULLS LAST",
        ),
        (
            "runtimes",
            "model_name",
            "metadata.name ASC NULLS LAST",
        ),
        (
            "runtimes",
            "role",
            "deployments.role ASC NULLS LAST",
        ),
        (
            "requests",
            "prediction",
            "executions.prediction ASC NULLS LAST",
        ),
        (
            "decisions",
            "model_name",
            "metadata.name ASC NULLS LAST",
        ),
        (
            "executions",
            "model_version",
            "versions.version ASC NULLS LAST",
        ),
    ],
)
async def test_search_records_sorts_related_fields(
        section: str,
        sort_by: str,
        expected_sql: str,
) -> None:
    """测试部署和 API 调用支持关联字段排序."""
    repository, execute = create_repository()

    await repository.search_records(
        section=section,
        query="",
        limit=11,
        offset=0,
        sort_by=sort_by,
        sort_order="asc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "LEFT OUTER JOIN" in sql
    assert expected_sql in sql


@pytest.mark.asyncio
async def test_search_records_supports_multiple_sort_fields() -> None:
    """测试按优先级应用多字段排序并追加稳定 ID."""
    repository, execute = create_repository()

    await repository.search_records(
        section="deployments",
        query="",
        limit=11,
        offset=0,
        sort_by="model_name,status",
        sort_order="asc,desc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert (
        "ORDER BY metadata.name ASC NULLS LAST, "
        "deployments.status DESC NULLS LAST, "
        "deployments.deployment_id ASC"
    ) in sql


@pytest.mark.asyncio
async def test_search_records_sorts_batch_requests_by_position() -> None:
    """测试批次请求按照批次位置排序."""
    repository, execute = create_repository()

    await repository.search_records(
        section="requests",
        query="batch_id:bat_test",
        limit=20,
        offset=0,
        sort_by="batch_index",
        sort_order="asc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert (
        "ORDER BY requests.batch_index ASC NULLS LAST, "
        "requests.request_id ASC"
    ) in sql


@pytest.mark.asyncio
async def test_search_records_filters_batch_attempts() -> None:
    """测试按照批次筛选并排序执行尝试."""
    repository, execute = create_repository()

    await repository.search_records(
        section="attempts",
        query="batch_id:bat_test%archive",
        limit=20,
        offset=0,
        sort_by="attempt_number",
        sort_order="asc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    sql = str(compiled)
    ilike_predicates = get_ilike_predicates(statement)
    assert "FROM attempts" in sql
    assert "attempts.batch_id ILIKE" in sql
    assert r"bat\_test\%archive" in compiled.params.values()
    assert len(ilike_predicates) == 1
    assert ilike_predicates[0].modifiers["escape"] == "\\"
    assert sql.count(" ESCAPE ") == len(ilike_predicates)
    assert (
        "ORDER BY attempts.attempt_number ASC NULLS LAST, "
        "attempts.attempt_id ASC"
    ) in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "query",
        "expected_pattern",
    ),
    [
        (
            "task_id:tsk_shard_test",
            r"tsk\_shard\_test",
        ),
        (
            "tsk_shard_test",
            r"%tsk\_shard\_test%",
        ),
    ],
)
async def test_search_attempts_matches_shard_task_id(
        query: str,
        expected_pattern: str,
) -> None:
    """测试通过分片任务 ID 查询所属执行尝试."""
    repository, execute = create_repository()

    await repository.search_records(
        section="attempts",
        query=query,
        limit=20,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    sql = str(compiled)
    ilike_predicates = get_ilike_predicates(statement)
    assert "EXISTS (SELECT shards.shard_id" in sql
    assert "shards.attempt_id = attempts.attempt_id" in sql
    assert "attempts.task_id ILIKE" in sql
    assert "shards.task_id ILIKE" in sql
    assert list(compiled.params.values()).count(expected_pattern) >= 2
    assert len(ilike_predicates) >= 2
    assert all(
        predicate.modifiers["escape"] == "\\"
        for predicate in ilike_predicates
    )
    assert sql.count(" ESCAPE ") == len(ilike_predicates)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "section",
        "expected_sql",
    ),
    [
        (
            "deployments",
            "ORDER BY deployments.updated_at DESC, deployments.created_at DESC",
        ),
        (
            "experiments",
            "ORDER BY experiments.updated_at DESC, experiments.created_at DESC",
        ),
    ],
)
async def test_search_records_defaults_to_updated_time(
        section: str,
        expected_sql: str,
) -> None:
    """测试资源列表默认按照更新时间倒序排列."""
    repository, execute = create_repository()

    await repository.search_records(
        section=section,
        query="",
        limit=11,
        offset=0,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert expected_sql in sql


@pytest.mark.asyncio
async def test_search_records_rejects_unknown_sort_field() -> None:
    """测试拒绝未列入白名单的排序字段."""
    repository, execute = create_repository()

    with pytest.raises(
            ValueError,
            match="不支持的排序字段: password_hash",
    ):
        await repository.search_records(
            section="models",
            query="",
            limit=11,
            offset=0,
            sort_by="password_hash",
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_version_labels() -> None:
    """测试批量获取版本对应的模型名称."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "version_id": "ver_test",
            "model_name": "scorecard",
            "display_name": "信用评分卡模型",
        }
    ]

    labels = await repository.get_version_labels([
        "ver_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM versions" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert labels == {
        "ver_test": {
            "model_name": "scorecard",
            "display_name": "信用评分卡模型",
        }
    }


@pytest.mark.asyncio
async def test_get_deployment_labels() -> None:
    """测试批量获取部署关联的模型、版本和发布信息."""
    repository, execute = create_repository()
    effective_from = datetime(
        2026,
        8,
        28,
        8,
        47,
        36,
        tzinfo=timezone.utc,
    )
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "deployment_id": "dep_test",
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "environment": "production",
            "rollout_type": "canary",
            "rollout_group": "challenger",
            "effective_from": effective_from,
            "effective_to": None,
        }
    ]

    labels = await repository.get_deployment_labels([
        "dep_test"
    ])

    assert labels == {
        "dep_test": {
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "environment": "production",
            "rollout_type": "canary",
            "rollout_group": "challenger",
            "effective_from": effective_from,
            "effective_to": None,
        }
    }


@pytest.mark.asyncio
async def test_get_request_details() -> None:
    """测试批量获取 API 调用的模型和决策详情."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "request_id": "req_test",
            "model_name": "scorecard",
            "task_type": "scoring",
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": {
                "score": 680
            },
            "version_id": "ver_test",
        }
    ]

    details = await repository.get_request_details([
        "req_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM requests" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN decisions" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert "LEFT OUTER JOIN executions" in sql
    assert (
        "decisions.decision_id = "
        "requests.latest_decision_id"
        in sql
    )
    assert details == {
        "req_test": {
            "model_name": "scorecard",
            "task_type": "scoring",
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": {
                "score": 680
            },
            "version_id": "ver_test",
        }
    }


@pytest.mark.asyncio
async def test_get_experiment_labels() -> None:
    """测试批量获取实验模型名称."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "experiment_id": "exp_test",
            "model_name": "scorecard",
        },
    ]

    labels = await repository.get_experiment_labels([
        "exp_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM experiments" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "JOIN variants" not in sql
    assert "JOIN versions" not in sql
    assert labels == {
        "exp_test": {
            "model_name": "scorecard",
        }
    }


@pytest.mark.asyncio
async def test_get_variant_labels() -> None:
    """测试批量获取分组对应的实验和模型信息."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "variant_id": "var_test",
            "experiment_name": "credit-policy",
            "experiment_status": "draft",
            "experiment_config": {
                "strategy": "hash",
                "traffic_ratio": 0.3,
            },
            "model_name": "scorecard",
            "model_version": "2.0.0",
        }
    ]

    labels = await repository.get_variant_labels([
        "var_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM variants" in sql
    assert "LEFT OUTER JOIN experiments" in sql
    assert "LEFT OUTER JOIN deployments" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert labels == {
        "var_test": {
            "experiment_name": "credit-policy",
            "experiment_status": "draft",
            "experiment_config": {
                "strategy": "hash",
                "traffic_ratio": 0.3,
            },
            "model_name": "scorecard",
            "model_version": "2.0.0",
        }
    }


@pytest.mark.asyncio
async def test_get_batch_deployment_stats() -> None:
    """测试批量获取批次实际命中的主执行和影子执行部署统计."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "batch_id": "bat_test",
            "deployment_id": "dep_primary",
            "execution_type": "primary",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "execution_count": 2,
        },
        {
            "batch_id": "bat_test",
            "deployment_id": "dep_shadow",
            "execution_type": "shadow",
            "model_name": "scorecard",
            "model_version": "2.0.0",
            "execution_count": 2,
        },
    ]

    deployments = await repository.get_batch_deployment_stats([
        "bat_test",
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM requests" in sql
    assert "JOIN decisions" in sql
    assert "JOIN executions" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert (
        "decisions.decision_id = "
        "requests.latest_decision_id"
        in sql
    )
    assert "GROUP BY requests.batch_id" in sql
    assert deployments == {
        "bat_test": [
            {
                "deployment_id": "dep_primary",
                "execution_type": "primary",
                "model_name": "scorecard",
                "model_version": "1.0.0",
                "execution_count": 2,
            },
            {
                "deployment_id": "dep_shadow",
                "execution_type": "shadow",
                "model_name": "scorecard",
                "model_version": "2.0.0",
                "execution_count": 2,
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_attempt_shard_details() -> None:
    """测试使用单条语句聚合执行尝试的分片进度."""
    repository, execute = create_repository()
    shard = Shard(
        shard_id="shd_test",
        attempt_id="att_test",
        batch_id="bat_test",
        task_id="tsk_test",
        start_index=0,
        end_index=20,
        status="running",
    )
    execute.return_value.all.return_value = [
        (
            shard,
            12,
            10,
            2,
        ),
    ]

    details = await repository.get_attempt_shard_details([
        "att_test",
    ])

    execute.assert_awaited_once()
    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "LEFT OUTER JOIN requests" in sql
    assert "requests.batch_id = shards.batch_id" in sql
    assert "requests.batch_index >= shards.start_index" in sql
    assert "requests.batch_index < shards.end_index" in sql
    assert "GROUP BY shards.id" in sql
    assert details == {
        "att_test": [
            {
                "record": shard,
                "total_count": 20,
                "completed_count": 12,
                "succeeded_count": 10,
                "failed_count": 2,
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_decision_details() -> None:
    """测试批量获取决策对应的模型和主执行详情."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "decision_id": "dcs_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "experiment_name": "credit-policy",
            "variant_name": "treatment",
            "variant_is_control": False,
            "variant_weight": 0.5,
            "deployment_role": "challenger",
            "deployment_rollout_type": "canary",
            "routing_id": "rtn_test",
            "routing_name": "scorecard-route",
            "routing_weight": 0.9,
            "prediction": {
                "score": 680,
            },
            "probability": 0.25,
            "score": 680.0,
            "latency_ms": 18.5,
        }
    ]

    details = await repository.get_decision_details([
        "dcs_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM decisions" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert "LEFT OUTER JOIN routing" in sql
    assert "LEFT OUTER JOIN experiments" in sql
    assert "LEFT OUTER JOIN variants" in sql
    assert "LEFT OUTER JOIN deployments" in sql
    assert "LEFT OUTER JOIN executions" in sql
    assert details == {
        "dcs_test": {
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "experiment_name": "credit-policy",
            "variant_name": "treatment",
            "variant_is_control": False,
            "variant_weight": 0.5,
            "deployment_role": "challenger",
            "deployment_rollout_type": "canary",
            "routing_id": "rtn_test",
            "routing_name": "scorecard-route",
            "routing_weight": 0.9,
            "prediction": {
                "score": 680,
            },
            "probability": 0.25,
            "score": 680.0,
            "latency_ms": 18.5,
        }
    }


@pytest.mark.asyncio
async def test_get_execution_details() -> None:
    """测试批量获取执行对应的请求和模型信息."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "execution_id": "exe_test",
            "request_id": "req_test",
            "model_name": "scorecard",
            "model_version": "2.0.0",
            "routing_name": "scorecard-primary-route",
            "routing_weight": 0.6,
        }
    ]

    details = await repository.get_execution_details([
        "exe_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM executions" in sql
    assert "LEFT OUTER JOIN decisions" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert "LEFT OUTER JOIN routing" in sql
    assert details == {
        "exe_test": {
            "request_id": "req_test",
            "model_name": "scorecard",
            "model_version": "2.0.0",
            "routing_name": "scorecard-primary-route",
            "routing_weight": 0.6,
        }
    }


@pytest.mark.asyncio
async def test_get_decision_executions() -> None:
    """测试批量获取决策对应的主执行和影子执行."""
    repository, execute = create_repository()
    primary = MagicMock(
        decision_id="dcs_test"
    )
    shadow = MagicMock(
        decision_id="dcs_test"
    )
    execute.return_value.all.return_value = [
        (
            primary,
            "scorecard",
            "1.0.0",
            "scorecard-primary-route",
            0.6,
        ),
        (
            shadow,
            "scorecard",
            "2.0.0",
            "scorecard-shadow-route",
            1.0,
        ),
    ]

    executions = await repository.get_decision_executions([
        "dcs_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM executions" in sql
    assert "LEFT OUTER JOIN metadata" in sql
    assert "LEFT OUTER JOIN versions" in sql
    assert "LEFT OUTER JOIN routing" in sql
    assert len(executions["dcs_test"]) == 2
    assert executions["dcs_test"][0] == {
        "execution": primary,
        "model_name": "scorecard",
        "model_version": "1.0.0",
        "routing_name": "scorecard-primary-route",
        "routing_weight": 0.6,
    }
    assert executions["dcs_test"][1] == {
        "execution": shadow,
        "model_name": "scorecard",
        "model_version": "2.0.0",
        "routing_name": "scorecard-shadow-route",
        "routing_weight": 1.0,
    }


@pytest.mark.asyncio
async def test_get_variant_counts() -> None:
    """测试批量统计实验分组数量."""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "experiment_id": "exp_test",
            "variant_count": 2,
        }
    ]

    counts = await repository.get_variant_counts([
        "exp_test"
    ])

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM variants" in sql
    assert "GROUP BY variants.experiment_id" in sql
    assert counts == {
        "exp_test": 2
    }


@pytest.mark.asyncio
async def test_search_variants() -> None:
    """测试查询、排序并分页返回实验分组."""
    repository, execute = create_repository()

    await repository.search_variants(
        experiment_id="exp_test",
        query="variant:control status:active",
        limit=11,
        offset=10,
        sort_by="weight",
        sort_order="desc",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM variants" in sql
    assert "variants.experiment_id = 'exp_test'" in sql
    assert "variants.name ILIKE" in sql
    assert "variants.status ILIKE" in sql
    assert sql.count("ILIKE") == 2
    assert "variants.weight DESC NULLS LAST" in sql
    assert "LIMIT 11 OFFSET 10" in sql


@pytest.mark.asyncio
async def test_get_request_trend() -> None:
    """测试使用 date_bin 按指定粒度查询 API 调用趋势."""
    repository, execute = create_repository()

    await repository.get_request_trend(
        since=datetime(
            2026,
            8,
            5,
            tzinfo=timezone.utc,
        ),
        interval=timedelta(
            minutes=5
        ),
        origin=datetime(
            2000,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "date_bin(" in sql
    assert "make_interval(secs=>300.0)" in sql
    assert "requests.created_at" in sql
    assert "FILTER (WHERE requests.status = 'success')" in sql
    assert "FILTER (WHERE requests.status = 'failed')" in sql
    assert "requests.created_at >=" in sql
    assert "GROUP BY" in sql
    assert "ORDER BY" in sql


@pytest.mark.asyncio
async def test_get_request_metrics() -> None:
    """测试查询当前和上一周期的 API 调用核心指标."""
    repository, execute = create_repository()
    result = execute.return_value
    result.mappings.return_value.one.return_value = {
        "request_count": 1284,
        "success_count": 1267,
        "failed_count": 17,
        "average_latency_ms": 436.25,
        "p95_latency_ms": 612.4,
        "previous_request_count": 1140,
    }

    metrics = await repository.get_request_metrics(
        since=datetime(
            2026,
            8,
            5,
            tzinfo=timezone.utc,
        ),
        previous_since=datetime(
            2026,
            8,
            4,
            tzinfo=timezone.utc,
        ),
    )

    assert metrics == {
        "request_count": 1284,
        "success_count": 1267,
        "failed_count": 17,
        "average_latency_ms": 436.25,
        "p95_latency_ms": 612.4,
        "previous_request_count": 1140,
    }
    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "percentile_cont(0.95) WITHIN GROUP" in sql
    assert "avg(requests.latency_ms) FILTER" in sql
    assert "requests.status = 'success'" in sql
    assert "requests.status = 'failed'" in sql
    assert "requests.created_at <" in sql


@pytest.mark.asyncio
async def test_get_model_request_stats() -> None:
    """测试查询模型最近表现和累计调用量."""
    repository, execute = create_repository()
    result = execute.return_value
    result.mappings.return_value.all.return_value = [
        {
            "model_id": "mdl_test",
            "model_name": "scorecard",
            "deleted_at": None,
            "recent_count": 8,
            "recent_success_count": 7,
            "average_latency_ms": 196.315,
            "total_count": 120,
            "recent_total_count": 10,
        },
        {
            "model_id": "mdl_idle",
            "model_name": "legacy",
            "deleted_at": datetime(
                2026,
                8,
                4,
                tzinfo=timezone.utc,
            ),
            "recent_count": 0,
            "recent_success_count": 0,
            "average_latency_ms": None,
            "total_count": 24,
            "recent_total_count": 10,
        }
    ]

    records = await repository.get_model_request_stats(
        since=datetime(
            2026,
            8,
            5,
            tzinfo=timezone.utc,
        ),
    )

    assert records == [
        {
            "model_id": "mdl_test",
            "model_name": "scorecard",
            "is_deleted": False,
            "recent_count": 8,
            "recent_success_count": 7,
            "average_latency_ms": 196.315,
            "total_count": 120,
            "recent_total_count": 10,
        },
        {
            "model_id": "mdl_idle",
            "model_name": "legacy",
            "is_deleted": True,
            "recent_count": 0,
            "recent_success_count": 0,
            "average_latency_ms": None,
            "total_count": 24,
            "recent_total_count": 10,
        }
    ]
    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM metadata LEFT OUTER JOIN requests" in sql
    assert "count(requests.request_id)" in sql
    assert "FILTER (WHERE requests.created_at >=" in sql
    assert "requests.status = 'success'" in sql
    assert "avg(requests.latency_ms) FILTER" in sql
    assert (
        "GROUP BY metadata.model_id, metadata.name, metadata.deleted_at"
        in sql
    )
    assert "HAVING count(requests.request_id) > 0" in sql
    assert "LIMIT" not in sql
