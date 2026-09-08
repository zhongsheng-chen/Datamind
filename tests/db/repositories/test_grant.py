"""角色授予仓储测试

验证角色授予查询、列表筛选、创建、重新激活和撤销能力。

核心功能：
  - test_get_grant_queries_by_grant_id:
    验证按授予 ID 查询
  - test_get_grant_queries_by_user_and_role:
    验证按用户和角色查询
  - test_get_grant_rejects_invalid_conditions:
    验证查询条件组合
  - test_list_grants_builds_query:
    验证授予列表筛选、排序和分页
  - test_list_active_grants_delegates_to_list_grants:
    验证有效授予列表复用通用查询
  - test_create_grant:
    验证创建角色授予记录
  - test_activate_grant:
    验证重新激活角色授予
  - test_revoke_grant:
    验证撤销角色授予
  - test_grant_status_operations_use_current_utc_time:
    验证状态操作默认使用当前 UTC 时间
"""

from datetime import (
    datetime,
    timezone,
    tzinfo,
)
from typing import (
    Any,
    Self,
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

import datamind.db.repositories.grant as grant_module
from datamind.auth.enums import GrantStatus
from datamind.db.models.grants import Grant
from datamind.db.repositories.grant import GrantRepository


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)


def create_grant(
        **overrides: Any,
) -> Grant:
    """创建角色授予测试对象"""
    values: dict[str, Any] = {
        "grant_id": "grt_0123456789abcdef",
        "user_id": "usr_0123456789abcdef",
        "role_id": "rol_0123456789abcdef",
        "status": str(
            GrantStatus.ACTIVE
        ),
        "granted_by": "usr_admin",
    }
    values.update(
        overrides
    )

    return Grant(
        **values
    )


def create_repository(
        *,
        scalar_result: Grant | None = None,
        list_result: list[Grant] | None = None,
) -> tuple[
    GrantRepository,
    MagicMock,
    AsyncMock,
]:
    """创建角色授予仓储及异步会话替身"""
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
    session = MagicMock(
        spec=AsyncSession
    )
    session.execute = execute

    repository = GrantRepository(
        cast(
            AsyncSession,
            session,
        )
    )

    return (
        repository,
        session,
        execute,
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


def get_executed_statement(
        execute: AsyncMock,
) -> Select[Any]:
    """获取异步会话最近执行的查询语句"""
    awaited_call = execute.await_args

    assert awaited_call is not None

    return cast(
        Select[Any],
        awaited_call.args[
            0
        ],
    )


@pytest.mark.asyncio
async def test_get_grant_queries_by_grant_id() -> None:
    """验证按授予 ID 查询"""
    expected_grant = create_grant()
    repository, _, execute = create_repository(
        scalar_result=expected_grant
    )

    result = await repository.get_grant(
        grant_id="grt_0123456789abcdef"
    )

    assert result is expected_grant
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "grants.grant_id = "
        "'grt_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_grant_queries_by_user_and_role() -> None:
    """验证按用户和角色查询"""
    expected_grant = create_grant()
    repository, _, execute = create_repository(
        scalar_result=expected_grant
    )

    result = await repository.get_grant(
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
    )

    assert result is expected_grant

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "grants.user_id = "
        "'usr_0123456789abcdef'"
        in sql
    )
    assert (
        "grants.role_id = "
        "'rol_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {
            "user_id": "usr_1",
        },
        {
            "role_id": "rol_1",
        },
        {
            "grant_id": "grt_1",
            "user_id": "usr_1",
            "role_id": "rol_1",
        },
    ],
)
async def test_get_grant_rejects_invalid_conditions(
        arguments: dict[str, str],
) -> None:
    """验证查询条件组合"""
    repository, _, execute = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "必须提供 grant_id，"
                "或者同时提供 user_id 和 role_id"
            ),
    ):
        await repository.get_grant(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_grant_returns_none_when_not_found() -> None:
    """验证角色授予不存在时返回 None"""
    repository, _, _ = create_repository(
        scalar_result=None
    )

    result = await repository.get_grant(
        grant_id="grt_missing"
    )

    assert result is None


@pytest.mark.asyncio
async def test_list_grants_uses_default_order_and_limit() -> None:
    """验证角色授予列表默认排序和数量限制"""
    grants = [
        create_grant()
    ]
    repository, _, execute = create_repository(
        list_result=grants
    )

    result = await repository.list_grants()

    assert result == grants
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY grants.granted_at DESC"
        in sql
    )
    assert "LIMIT 100" in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_grants_builds_filtered_query() -> None:
    """验证授予列表筛选、排序和分页"""
    grants = [
        create_grant(
            status=str(
                GrantStatus.REVOKED
            )
        )
    ]
    repository, _, execute = create_repository(
        list_result=grants
    )

    result = await repository.list_grants(
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status=GrantStatus.REVOKED,
        limit=25,
        offset=10,
    )

    assert result == grants

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "grants.user_id = "
        "'usr_0123456789abcdef'"
        in sql
    )
    assert (
        "grants.role_id = "
        "'rol_0123456789abcdef'"
        in sql
    )
    assert (
        "grants.status = 'revoked'"
        in sql
    )
    assert (
        "ORDER BY grants.granted_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_grants_allows_unlimited_query() -> None:
    """验证授予列表允许不设置分页"""
    repository, _, execute = create_repository()

    await repository.list_grants(
        limit=None,
        offset=None,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_active_grants_delegates_to_list_grants(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证有效授予列表复用通用查询"""
    grants = [
        create_grant()
    ]
    repository, _, _ = create_repository()
    list_grants = AsyncMock(
        return_value=grants
    )

    monkeypatch.setattr(
        repository,
        "list_grants",
        list_grants,
    )

    result = await repository.list_active_grants(
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        limit=50,
        offset=5,
    )

    assert result == grants
    list_grants.assert_awaited_once_with(
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status=GrantStatus.ACTIVE,
        limit=50,
        offset=5,
    )


# noinspection PyUnreachableCode
def test_create_grant_uses_defaults() -> None:
    """验证创建默认有效角色授予"""
    repository, session, _ = create_repository()

    grant = repository.create_grant(
        grant_id="grt_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
    )

    session.add.assert_called_once_with(
        grant
    )
    assert grant.grant_id == (
        "grt_0123456789abcdef"
    )
    assert grant.user_id == (
        "usr_0123456789abcdef"
    )
    assert grant.role_id == (
        "rol_0123456789abcdef"
    )
    assert grant.status == "active"
    assert grant.granted_by is None


def test_create_grant_with_explicit_values() -> None:
    """验证创建指定状态和授予时间的记录"""
    repository, session, _ = create_repository()

    grant = repository.create_grant(
        grant_id="grt_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status=GrantStatus.REVOKED,
        granted_by="usr_admin",
        granted_at=CURRENT_TIME,
    )

    session.add.assert_called_once_with(
        grant
    )
    assert grant.status == "revoked"
    assert grant.granted_by == "usr_admin"
    assert grant.granted_at == CURRENT_TIME


# noinspection PyUnreachableCode
def test_activate_grant_with_explicit_time() -> None:
    """验证使用指定时间重新激活角色授予"""
    repository, _, _ = create_repository()
    grant = create_grant(
        status=str(
            GrantStatus.REVOKED
        ),
        granted_by="usr_original",
        revoked_by="usr_revoker",
        revoked_at=CURRENT_TIME,
    )

    result = repository.activate_grant(
        grant,
        granted_by="usr_operator",
        granted_at=CURRENT_TIME,
    )

    assert result is grant
    assert grant.status == "active"
    assert grant.granted_by == "usr_operator"
    assert grant.granted_at == CURRENT_TIME
    assert grant.revoked_by is None
    assert grant.revoked_at is None


# noinspection PyUnreachableCode
def test_activate_grant_allows_empty_granted_by() -> None:
    """验证重新激活时允许不记录授予用户"""
    repository, _, _ = create_repository()
    grant = create_grant(
        status=str(
            GrantStatus.REVOKED
        ),
        granted_by="usr_original",
        revoked_by="usr_revoker",
        revoked_at=CURRENT_TIME,
    )

    repository.activate_grant(
        grant,
        granted_at=CURRENT_TIME,
    )

    assert grant.granted_by is None


def test_revoke_grant_with_explicit_time() -> None:
    """验证使用指定时间撤销角色授予"""
    repository, _, _ = create_repository()
    grant = create_grant()
    original_granted_by = grant.granted_by

    result = repository.revoke_grant(
        grant,
        revoked_by="usr_operator",
        revoked_at=CURRENT_TIME,
    )

    assert result is grant
    assert grant.status == "revoked"
    assert grant.revoked_by == "usr_operator"
    assert grant.revoked_at == CURRENT_TIME
    assert grant.granted_by == original_granted_by


# noinspection PyUnreachableCode
@pytest.mark.parametrize(
    "operation_name",
    [
        "activate_grant",
        "revoke_grant",
    ],
)
def test_grant_status_operations_use_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
        operation_name: str,
) -> None:
    """验证状态操作默认使用当前 UTC 时间"""
    class FrozenDateTime(
        datetime
    ):
        @classmethod
        def now(
                cls,
                tz: tzinfo | None = None,
        ) -> Self:
            assert tz is timezone.utc

            return cls.fromtimestamp(
                CURRENT_TIME.timestamp(),
                tz,
            )

    repository, _, _ = create_repository()
    grant = create_grant(
        status=str(
            GrantStatus.REVOKED
        )
        if operation_name == "activate_grant"
        else str(
            GrantStatus.ACTIVE
        ),
        revoked_at=CURRENT_TIME
        if operation_name == "activate_grant"
        else None,
    )

    monkeypatch.setitem(
        vars(grant_module),
        "datetime",
        FrozenDateTime,
    )

    operation = getattr(
        repository,
        operation_name,
    )
    operation(
        grant
    )

    if operation_name == "activate_grant":
        assert grant.granted_at == CURRENT_TIME
        assert grant.revoked_at is None
    else:
        assert grant.revoked_at == CURRENT_TIME
