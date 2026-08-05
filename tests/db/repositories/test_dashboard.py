# tests/db/repositories/test_dashboard.py

"""管理控制台查询仓储测试

验证控制台页面记录总数、关键词查询和参数校验。

核心功能：
  - test_get_counts: 验证查询指定页面记录总数
  - test_get_counts_rejects_unknown_section: 验证拒绝未知页面
  - test_get_counts_returns_empty_without_sections: 验证空页面集合
  - test_get_request_trend: 验证 API 调用趋势查询
  - test_get_variant_counts: 验证实验分组数量查询
  - test_search_records: 验证关键词查询和分页
  - test_search_records_sorts_related_fields: 验证关联字段排序
  - test_search_variants: 验证实验分组查询和排序
"""

from datetime import (
    datetime,
    timezone,
)
from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.repositories.dashboard import DashboardRepository


def create_repository() -> tuple[DashboardRepository, AsyncMock]:
    """创建控制台统计仓储及会话替身"""
    result = MagicMock()
    result.mappings.return_value.one.return_value = {
        "models": 4,
        "audits": 33,
    }
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
    """测试使用单条语句查询指定页面记录总数"""
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


@pytest.mark.asyncio
async def test_get_counts_rejects_unknown_section() -> None:
    """测试拒绝未知控制台页面"""
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
    """测试空页面集合不查询数据库"""
    repository, execute = create_repository()

    counts = await repository.get_counts([])

    assert counts == {}
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_records() -> None:
    """测试模型页面使用关键词查询并分页"""
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
    assert "LIMIT 11 OFFSET 10" in sql


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
            "requests",
            "prediction",
            "decisions.prediction ASC NULLS LAST",
        ),
        (
            "decisions",
            "model_name",
            "metadata.name ASC NULLS LAST",
        ),
    ],
)
async def test_search_records_sorts_related_fields(
        section: str,
        sort_by: str,
        expected_sql: str,
) -> None:
    """测试部署和 API 调用支持关联字段排序"""
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
    """测试资源列表默认按照更新时间倒序排列"""
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
    """测试拒绝未列入白名单的排序字段"""
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
async def test_get_request_details() -> None:
    """测试批量获取 API 调用的模型和决策详情"""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "request_id": "req_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": {
                "score": 680
            },
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
    assert details == {
        "req_test": {
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": {
                "score": 680
            },
        }
    }


@pytest.mark.asyncio
async def test_get_decision_labels() -> None:
    """测试批量获取决策对应的模型名称和版本号"""
    repository, execute = create_repository()
    execute.return_value.mappings.return_value.all.return_value = [
        {
            "decision_id": "dcs_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
        }
    ]

    labels = await repository.get_decision_labels([
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
    assert labels == {
        "dcs_test": {
            "model_name": "scorecard",
            "model_version": "1.0.0",
        }
    }


@pytest.mark.asyncio
async def test_get_variant_counts() -> None:
    """测试批量统计实验分组数量"""
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
    """测试查询、排序并分页返回实验分组"""
    repository, execute = create_repository()

    await repository.search_variants(
        experiment_id="exp_test",
        query="control",
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
    assert "ILIKE" in sql
    assert "variants.weight DESC NULLS LAST" in sql
    assert "LIMIT 11 OFFSET 10" in sql


@pytest.mark.asyncio
async def test_get_request_trend() -> None:
    """测试按小时查询 API 调用趋势"""
    repository, execute = create_repository()

    await repository.get_request_trend(
        since=datetime(
            2026,
            8,
            5,
            tzinfo=timezone.utc,
        )
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
    assert "date_trunc('hour', requests.created_at)" in sql
    assert "FILTER (WHERE requests.status = 'success')" in sql
    assert "FILTER (WHERE requests.status = 'failed')" in sql
    assert "requests.created_at >=" in sql
    assert "GROUP BY" in sql
    assert "ORDER BY" in sql
