# tests/db/repositories/test_routing.py

"""路由仓储测试

验证 RoutingRepository 的路由查询、列表筛选、创建、
普通字段更新，以及启用和禁用生命周期管理。

核心功能：
  - test_get_routing:
    验证按路由 ID 查询
  - test_list_routings:
    验证环境、启用状态、排序和分页
  - test_list_enabled_routings:
    验证获取启用的路由规则
  - test_routing_patch:
    验证更新结构和环境枚举
  - test_create_routing:
    验证创建路由规则和流量比例
  - test_update_routing:
    验证普通路由字段更新
  - test_enable_routing:
    验证启用路由规则
  - test_disable_routing:
    验证禁用路由规则
"""

from dataclasses import fields
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
from sqlalchemy.sql import Select

from datamind.constants import Environment
from datamind.db.models.routing import Routing
from datamind.db.repositories.routing import (
    RoutingPatch,
    RoutingRepository,
)


def create_routing(
        **overrides: Any,
) -> Routing:
    """创建路由规则测试对象"""
    values: dict[str, Any] = {
        "routing_id": "rtn_0123456789abcdef",
        "deployment_id": "dep_0123456789abcdef",
        "rollout_type": "full",
        "rollout_group": "champion",
        "environment": "production",
        "enabled": True,
        "traffic_ratio": 0.3,
        "rules": {
            "match": "all",
        },
        "description": "信用评分模型路由",
        "created_by": "creator",
        "updated_by": "original_operator",
    }
    values.update(
        overrides
    )

    return Routing(
        **values
    )


def create_repository(
        *,
        scalar_result: Routing | None = None,
        list_result: list[Routing] | None = None,
) -> tuple[
    RoutingRepository,
    AsyncMock,
    MagicMock,
]:
    """创建路由仓储及会话方法替身"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        scalar_result
    )

    scalar_collection = MagicMock()
    scalar_collection.all.return_value = (
        list_result
        if list_result is not None
        else []
    )
    result.scalars.return_value = (
        scalar_collection
    )

    execute = AsyncMock(
        return_value=result
    )
    add = MagicMock()

    session_mock = MagicMock(
        spec=AsyncSession
    )
    session_mock.execute = execute
    session_mock.add = add

    session = cast(
        AsyncSession,
        cast(
            object,
            session_mock,
        ),
    )
    repository = RoutingRepository(
        session
    )

    return (
        repository,
        execute,
        add,
    )


def get_executed_statement(
        execute: AsyncMock,
) -> Select[Any]:
    """获取异步会话执行的查询语句"""
    awaited_call = execute.await_args

    assert awaited_call is not None

    return cast(
        Select[Any],
        awaited_call.args[
            0
        ],
    )


def compile_statement(
        statement: Select[Any],
) -> str:
    """将查询语句编译为 PostgreSQL SQL"""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )


@pytest.mark.asyncio
async def test_get_routing() -> None:
    """验证按路由 ID 查询"""
    expected = create_routing()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_routing(
        "rtn_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "routing.routing_id = "
        "'rtn_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_routing_returns_none_when_not_found() -> None:
    """验证路由规则不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_routing(
        "rtn_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_routings_without_filters() -> None:
    """验证无筛选时返回全部路由并按时间倒序"""
    routings = [
        create_routing()
    ]
    repository, execute, _ = create_repository(
        list_result=routings
    )

    result = await repository.list_routings()

    assert result == routings

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY routing.updated_at DESC, "
        "routing.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_routings_applies_filters_and_pagination() -> None:
    """验证环境、启用状态、普通字段筛选和分页"""
    routings = [
        create_routing(
            rollout_type="canary",
            rollout_group="challenger",
            environment="staging",
            enabled=False,
        )
    ]
    repository, execute, _ = create_repository(
        list_result=routings
    )

    result = await repository.list_routings(
        routing_id="rtn_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        rollout_type="canary",
        rollout_group="challenger",
        environment=Environment.STAGING,
        enabled=False,
        created_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == routings

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "routing.routing_id = "
        "'rtn_0123456789abcdef'"
        in sql
    )
    assert (
        "routing.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "routing.rollout_type = 'canary'"
        in sql
    )
    assert (
        "routing.rollout_group = 'challenger'"
        in sql
    )
    assert (
        "routing.environment = 'staging'"
        in sql
    )
    assert "routing.enabled = false" in sql
    assert (
        "routing.created_by = 'model_admin'"
        in sql
    )
    assert (
        "ORDER BY routing.updated_at DESC, "
        "routing.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_routings_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_routings(
        limit=0,
        offset=0,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "LIMIT 0" in sql
    assert "OFFSET 0" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "arguments",
        "expected_message",
    ),
    [
        (
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            {
                "limit": -1,
                "offset": -1,
            },
            "limit 不能小于 0",
        ),
    ],
)
async def test_list_routings_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """验证拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_routings(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_enabled_routings() -> None:
    """验证获取指定部署和环境中的启用路由"""
    routings = [
        create_routing(
            enabled=True
        )
    ]
    repository, execute, _ = create_repository(
        list_result=routings
    )

    result = await repository.list_enabled_routings(
        deployment_id="dep_0123456789abcdef",
        environment=Environment.PRODUCTION,
        limit=50,
        offset=5,
    )

    assert result == routings

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "routing.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "routing.environment = 'production'"
        in sql
    )
    assert "routing.enabled = true" in sql
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_routing_patch_fields_and_defaults() -> None:
    """验证更新结构字段和默认值"""
    patch = RoutingPatch()

    assert [
        field.name
        for field in fields(
            RoutingPatch
        )
    ] == [
        "rollout_type",
        "rollout_group",
        "environment",
        "traffic_ratio",
        "rules",
        "description",
    ]
    assert patch.rollout_type is None
    assert patch.rollout_group is None
    assert patch.environment is None
    assert patch.traffic_ratio is None
    assert patch.rules is None
    assert patch.description is None
    assert not hasattr(
        patch,
        "enabled",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_routing_patch_accepts_environment_enum() -> None:
    """验证更新结构接受环境枚举"""
    patch = RoutingPatch(
        environment=Environment.STAGING
    )

    assert patch.environment is (
        Environment.STAGING
    )


# noinspection PyUnreachableCode
def test_create_routing() -> None:
    """验证创建路由规则"""
    repository, _, add = create_repository()

    routing = repository.create_routing(
        routing_id="rtn_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        environment=Environment.PRODUCTION,
        rollout_type="canary",
        rollout_group="challenger",
        traffic_ratio=0.3,
        enabled=False,
        rules={
            "match": "all",
        },
        description="灰度路由",
        created_by="creator",
    )

    add.assert_called_once_with(
        routing
    )
    assert routing.routing_id == (
        "rtn_0123456789abcdef"
    )
    assert routing.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert routing.environment == "production"
    assert routing.rollout_type == "canary"
    assert routing.rollout_group == (
        "challenger"
    )
    assert routing.traffic_ratio == 0.3
    assert routing.enabled is False
    assert routing.rules == {
        "match": "all",
    }
    assert routing.description == "灰度路由"
    assert routing.created_by == "creator"


# noinspection PyUnreachableCode
def test_create_routing_uses_optional_defaults() -> None:
    """验证创建路由规则的可选默认值"""
    repository, _, add = create_repository()

    routing = repository.create_routing(
        routing_id="rtn_minimum",
        deployment_id="dep_minimum",
        environment=Environment.TESTING,
    )

    add.assert_called_once_with(
        routing
    )
    assert routing.environment == "testing"
    assert routing.rollout_type == "full"
    assert routing.rollout_group is None
    assert routing.traffic_ratio == 0.0
    assert routing.enabled is True
    assert routing.rules is None
    assert routing.description is None
    assert routing.created_by is None


@pytest.mark.parametrize(
    "traffic_ratio",
    [
        0.0,
        1.0,
    ],
)
def test_create_routing_accepts_boundary_ratio(
        traffic_ratio: float,
) -> None:
    """验证流量比例边界值有效"""
    repository, _, add = create_repository()

    routing = repository.create_routing(
        routing_id="rtn_boundary",
        deployment_id="dep_boundary",
        environment=Environment.PRODUCTION,
        traffic_ratio=traffic_ratio,
    )

    add.assert_called_once_with(
        routing
    )
    assert routing.traffic_ratio == (
        traffic_ratio
    )


@pytest.mark.parametrize(
    "traffic_ratio",
    [
        -0.01,
        1.01,
    ],
)
def test_create_routing_rejects_invalid_ratio(
        traffic_ratio: float,
) -> None:
    """验证创建时拒绝非法流量比例"""
    repository, _, add = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "路由 traffic_ratio "
                "必须在 0 到 1 之间"
            ),
    ):
        repository.create_routing(
            routing_id="rtn_invalid",
            deployment_id="dep_invalid",
            environment=Environment.PRODUCTION,
            traffic_ratio=traffic_ratio,
        )

    add.assert_not_called()


def test_update_routing() -> None:
    """验证更新所有非空普通路由字段"""
    repository, _, _ = create_repository()
    routing = create_routing()
    original_enabled = routing.enabled

    result = repository.update_routing(
        routing,
        RoutingPatch(
            rollout_type="canary",
            rollout_group="challenger",
            environment=Environment.STAGING,
            traffic_ratio=0.5,
            rules={
                "match": "any",
            },
            description="更新后的路由说明",
        ),
        updated_by="operator",
    )

    assert result is routing
    assert routing.rollout_type == "canary"
    assert routing.rollout_group == (
        "challenger"
    )
    assert routing.environment == "staging"
    assert routing.traffic_ratio == 0.5
    assert routing.rules == {
        "match": "any",
    }
    assert routing.description == (
        "更新后的路由说明"
    )
    assert routing.updated_by == "operator"
    assert routing.enabled is original_enabled


def test_update_routing_ignores_none_fields() -> None:
    """验证值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    routing = create_routing()

    result = repository.update_routing(
        routing,
        RoutingPatch(),
    )

    assert result is routing
    assert routing.rollout_type == "full"
    assert routing.rollout_group == "champion"
    assert routing.environment == "production"
    assert routing.traffic_ratio == 0.3
    assert routing.description == (
        "信用评分模型路由"
    )


def test_update_routing_accepts_empty_strings() -> None:
    """验证空字符串作为明确更新值写入对象"""
    repository, _, _ = create_repository()
    routing = create_routing()

    repository.update_routing(
        routing,
        RoutingPatch(
            rollout_type="",
            rollout_group="",
            description="",
        ),
        updated_by="",
    )

    assert routing.rollout_type == ""
    assert routing.rollout_group == ""
    assert routing.description == ""
    assert routing.updated_by == ""


@pytest.mark.parametrize(
    "traffic_ratio",
    [
        -0.01,
        1.01,
    ],
)
def test_update_routing_rejects_invalid_ratio(
        traffic_ratio: float,
) -> None:
    """验证更新时拒绝非法流量比例"""
    repository, _, _ = create_repository()
    routing = create_routing()
    original_ratio = routing.traffic_ratio
    original_environment = routing.environment

    with pytest.raises(
            ValueError,
            match=(
                "路由 traffic_ratio "
                "必须在 0 到 1 之间"
            ),
    ):
        repository.update_routing(
            routing,
            RoutingPatch(
                environment=Environment.STAGING,
                traffic_ratio=traffic_ratio,
            ),
            updated_by="operator",
        )

    assert routing.traffic_ratio == original_ratio
    assert (
        routing.environment
        == original_environment
    )
    assert routing.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_enable_routing() -> None:
    """验证启用路由规则"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=False
    )

    result = repository.enable_routing(
        routing,
        updated_by="operator",
    )

    assert result is routing
    assert routing.enabled is True
    assert routing.updated_by == "operator"


# noinspection PyUnreachableCode
def test_enable_routing_without_operator() -> None:
    """验证启用时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=False,
        updated_by="original_operator",
    )

    repository.enable_routing(
        routing
    )

    assert routing.enabled is True
    assert routing.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_enable_routing_accepts_empty_operator() -> None:
    """验证启用时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=False
    )

    repository.enable_routing(
        routing,
        updated_by="",
    )

    assert routing.enabled is True
    assert routing.updated_by == ""


# noinspection PyUnreachableCode
def test_enable_routing_is_idempotent() -> None:
    """验证重复启用保持幂等"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=True,
        updated_by="original_operator",
    )

    result = repository.enable_routing(
        routing,
        updated_by="new_operator",
    )

    assert result is routing
    assert routing.enabled is True
    assert routing.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_disable_routing() -> None:
    """验证禁用路由规则"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=True
    )

    result = repository.disable_routing(
        routing,
        updated_by="operator",
    )

    assert result is routing
    assert routing.enabled is False
    assert routing.updated_by == "operator"


# noinspection PyUnreachableCode
def test_disable_routing_without_operator() -> None:
    """验证禁用时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=True,
        updated_by="original_operator",
    )

    repository.disable_routing(
        routing
    )

    assert routing.enabled is False
    assert routing.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_disable_routing_accepts_empty_operator() -> None:
    """验证禁用时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=True
    )

    repository.disable_routing(
        routing,
        updated_by="",
    )

    assert routing.enabled is False
    assert routing.updated_by == ""


# noinspection PyUnreachableCode
def test_disable_routing_is_idempotent() -> None:
    """验证重复禁用保持幂等"""
    repository, _, _ = create_repository()
    routing = create_routing(
        enabled=False,
        updated_by="original_operator",
    )

    result = repository.disable_routing(
        routing,
        updated_by="new_operator",
    )

    assert result is routing
    assert routing.enabled is False
    assert routing.updated_by == (
        "original_operator"
    )
