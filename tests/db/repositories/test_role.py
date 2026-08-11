# tests/db/repositories/test_role.py

"""角色仓储测试

验证角色查询、列表筛选、创建、基础信息更新、
权限替换和状态管理能力。

核心功能：
  - test_get_role_queries_by_single_condition:
    验证按角色 ID 或名称查询
  - test_get_role_rejects_invalid_conditions:
    验证查询条件必须且只能提供一个
  - test_list_roles_builds_query:
    验证角色列表筛选、排序和分页
  - test_list_active_roles_delegates_to_list_roles:
    验证活跃角色列表复用通用查询
  - test_role_patch:
    验证角色更新结构
  - test_create_role:
    验证创建角色
  - test_update_role:
    验证角色基础信息更新
  - test_replace_permissions:
    验证替换和清空角色权限
  - test_role_status_transitions:
    验证角色启用和停用
  - test_restore_role:
    验证恢复已逻辑删除的角色
"""

from datetime import (
    datetime,
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
from sqlalchemy.sql import Select

from datamind.auth.enums import RoleStatus
from datamind.db.models.roles import Role
from datamind.db.repositories.role import (
    RolePatch,
    RoleRepository,
)


CURRENT_TIME = datetime(
    2026,
    8,
    3,
    9,
    30,
    tzinfo=timezone.utc,
)


def create_role(
        **overrides: Any,
) -> Role:
    """创建角色测试对象"""
    values: dict[str, Any] = {
        "role_id": "rol_0123456789abcdef",
        "name": "admin",
        "description": "系统管理员",
        "permissions": [
            "model.*",
            "deployment.*",
        ],
        "status": str(
            RoleStatus.ACTIVE
        ),
        "created_by": "usr_admin",
    }
    values.update(
        overrides
    )

    return Role(
        **values
    )


def create_repository(
        *,
        scalar_result: Role | None = None,
        list_result: list[Role] | None = None,
) -> tuple[
    RoleRepository,
    MagicMock,
    AsyncMock,
]:
    """创建角色仓储及异步会话替身"""
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

    repository = RoleRepository(
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "arguments",
        "expected_condition",
    ),
    [
        (
            {
                "role_id": "rol_0123456789abcdef",
            },
            (
                "roles.role_id = "
                "'rol_0123456789abcdef'"
            ),
        ),
        (
            {
                "name": "admin",
            },
            "roles.name = 'admin'",
        ),
    ],
)
async def test_get_role_queries_by_single_condition(
        arguments: dict[str, str],
        expected_condition: str,
) -> None:
    """验证按角色 ID 或名称查询"""
    expected_role = create_role()
    repository, _, execute = create_repository(
        scalar_result=expected_role
    )

    result = await repository.get_role(
        **arguments
    )

    assert result is expected_role
    execute.assert_awaited_once()

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert expected_condition in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {
            "role_id": "rol_1",
            "name": "admin",
        },
    ],
)
async def test_get_role_rejects_invalid_conditions(
        arguments: dict[str, str],
) -> None:
    """验证查询条件必须且只能提供一个"""
    repository, _, execute = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "role_id、name "
                "必须且只能提供一个"
            ),
    ):
        await repository.get_role(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_role_returns_none_when_not_found() -> None:
    """验证角色不存在时返回 None"""
    repository, _, _ = create_repository(
        scalar_result=None
    )

    result = await repository.get_role(
        name="missing-role"
    )

    assert result is None


@pytest.mark.asyncio
async def test_list_roles_uses_default_order_and_limit() -> None:
    """验证角色列表默认排序和数量限制"""
    roles = [
        create_role()
    ]
    repository, _, execute = create_repository(
        list_result=roles
    )

    result = await repository.list_roles()

    assert result == roles
    execute.assert_awaited_once()

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert "ORDER BY roles.created_at DESC" in sql
    assert "LIMIT 100" in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_roles_builds_filtered_query() -> None:
    """验证角色列表筛选、排序和分页"""
    roles = [
        create_role(
            status=str(
                RoleStatus.INACTIVE
            )
        )
    ]
    repository, _, execute = create_repository(
        list_result=roles
    )

    result = await repository.list_roles(
        status=RoleStatus.INACTIVE,
        limit=25,
        offset=10,
    )

    assert result == roles

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert "roles.status = 'inactive'" in sql
    assert "ORDER BY roles.created_at DESC" in sql
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_roles_allows_unlimited_query() -> None:
    """验证角色列表允许不设置分页"""
    repository, _, execute = create_repository()

    await repository.list_roles(
        limit=None,
        offset=None,
    )

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_active_roles_delegates_to_list_roles(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证活跃角色列表复用通用查询"""
    roles = [
        create_role()
    ]
    repository, _, _ = create_repository()
    list_roles = AsyncMock(
        return_value=roles
    )

    monkeypatch.setattr(
        repository,
        "list_roles",
        list_roles,
    )

    result = await repository.list_active_roles(
        limit=50,
        offset=5,
    )

    assert result == roles
    list_roles.assert_awaited_once_with(
        status=RoleStatus.ACTIVE,
        limit=50,
        offset=5,
    )


def test_role_patch_uses_slots_and_defaults() -> None:
    """验证角色更新结构默认值和 slots"""
    patch = RolePatch()

    assert patch.name is None
    assert patch.description is None
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_create_role() -> None:
    """验证创建角色并加入数据库会话"""
    repository, session, _ = create_repository()
    permissions = [
        "model.*",
        "deployment.*",
    ]

    role = repository.create_role(
        role_id="rol_0123456789abcdef",
        name="admin",
        description="系统管理员",
        permissions=permissions,
        status=RoleStatus.ACTIVE,
        created_by="usr_admin",
    )

    session.add.assert_called_once_with(
        role
    )
    assert role.role_id == "rol_0123456789abcdef"
    assert role.name == "admin"
    assert role.description == "系统管理员"
    assert role.permissions == permissions
    assert role.status == "active"
    assert role.created_by == "usr_admin"


# noinspection PyUnreachableCode
def test_create_role_uses_defaults() -> None:
    """验证创建角色默认状态和可选字段"""
    repository, session, _ = create_repository()

    role = repository.create_role(
        role_id="rol_reader",
        name="reader",
    )

    session.add.assert_called_once_with(
        role
    )
    assert role.description is None
    assert role.permissions is None
    assert role.status == "active"
    assert role.created_by is None


def test_create_inactive_role() -> None:
    """验证创建停用角色时转换枚举值"""
    repository, _, _ = create_repository()

    role = repository.create_role(
        role_id="rol_inactive",
        name="inactive-role",
        status=RoleStatus.INACTIVE,
    )

    assert role.status == "inactive"


def test_update_role() -> None:
    """验证角色基础信息更新"""
    repository, _, _ = create_repository()
    role = create_role()
    original_permissions = role.permissions
    original_status = role.status

    result = repository.update_role(
        role,
        patch=RolePatch(
            name="administrator",
            description="平台系统管理员",
        ),
        updated_by="usr_operator",
    )

    assert result is role
    assert role.name == "administrator"
    assert role.description == "平台系统管理员"
    assert role.permissions is original_permissions
    assert role.status == original_status
    assert role.updated_by == "usr_operator"


def test_update_role_ignores_none_fields() -> None:
    """验证角色更新忽略值为 None 的字段"""
    repository, _, _ = create_repository()
    role = create_role(
        updated_by="usr_original"
    )

    repository.update_role(
        role,
        patch=RolePatch(
            description="新的角色说明",
        ),
    )

    assert role.name == "admin"
    assert role.description == "新的角色说明"
    assert role.updated_by == "usr_original"


def test_replace_permissions() -> None:
    """验证替换角色权限"""
    repository, _, _ = create_repository()
    role = create_role()
    permissions = [
        "model.read",
        "deployment.read",
    ]

    result = repository.replace_permissions(
        role,
        permissions=permissions,
        updated_by="usr_operator",
    )

    assert result is role
    assert role.permissions is permissions
    assert role.updated_by == "usr_operator"


def test_replace_permissions_with_empty_list() -> None:
    """验证使用空列表移除全部权限"""
    repository, _, _ = create_repository()
    role = create_role()

    repository.replace_permissions(
        role,
        permissions=[],
    )

    assert role.permissions == []


# noinspection PyUnreachableCode
def test_replace_permissions_with_none() -> None:
    """验证使用 None 清空角色权限配置"""
    repository, _, _ = create_repository()
    role = create_role(
        updated_by="usr_original"
    )

    repository.replace_permissions(
        role,
        permissions=None,
    )

    assert role.permissions is None
    assert role.updated_by == "usr_original"


def test_activate_role() -> None:
    """验证启用角色"""
    repository, _, _ = create_repository()
    role = create_role(
        status=str(
            RoleStatus.INACTIVE
        )
    )

    result = repository.activate_role(
        role,
        updated_by="usr_operator",
    )

    assert result is role
    assert role.status == "active"
    assert role.updated_by == "usr_operator"


def test_deactivate_role() -> None:
    """验证停用角色"""
    repository, _, _ = create_repository()
    role = create_role()

    result = repository.deactivate_role(
        role,
        updated_by="usr_operator",
    )

    assert result is role
    assert role.status == "inactive"
    assert role.updated_by == "usr_operator"


def test_replace_description_allows_clearing() -> None:
    """验证角色描述可以更新或清空"""
    repository, _, _ = create_repository()
    role = create_role(
        description="旧描述"
    )

    repository.replace_description(
        role,
        description=None,
        updated_by="usr_operator",
    )

    assert role.description is None
    assert role.updated_by == "usr_operator"


# noinspection PyUnreachableCode
def test_mark_deleted_role() -> None:
    """验证逻辑删除角色并保留授权历史"""
    repository, _, _ = create_repository()
    role = create_role(
        deleted_at=None
    )

    result = repository.mark_deleted(
        role,
        deleted_by="usr_admin",
        deletion_reason="角色停用",
        deleted_at=CURRENT_TIME,
    )

    assert result is role
    assert role.status == "inactive"
    assert role.deleted_at == CURRENT_TIME
    assert role.deleted_by == "usr_admin"
    assert role.deletion_reason == "角色停用"
    assert role.updated_by == "usr_admin"


# noinspection PyUnreachableCode
def test_restore_role() -> None:
    """验证恢复已逻辑删除的角色"""
    repository, _, _ = create_repository()
    role = create_role(
        status="inactive",
        deleted_at=CURRENT_TIME,
        deleted_by="usr_admin",
        deletion_reason="角色停用",
    )

    result = repository.restore_role(
        role,
        restored_at=CURRENT_TIME,
        restored_by="usr_operator",
    )

    assert result is role
    assert role.status == "active"
    assert role.created_at == CURRENT_TIME
    assert role.deleted_at is None
    assert role.deleted_by is None
    assert role.deletion_reason is None
    assert role.updated_by == "usr_operator"


@pytest.mark.parametrize(
    "operation_name",
    [
        "activate_role",
        "deactivate_role",
    ],
)
def test_role_status_update_preserves_existing_updated_by(
        operation_name: str,
) -> None:
    """验证未提供更新人时保留原更新人"""
    repository, _, _ = create_repository()
    role = create_role(
        updated_by="usr_original"
    )
    operation = getattr(
        repository,
        operation_name,
    )

    operation(
        role
    )

    assert role.updated_by == "usr_original"
