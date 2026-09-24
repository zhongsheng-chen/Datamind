"""用户仓储测试.

验证用户查询、列表筛选、创建、资料更新、密码更新、
状态流转和登录状态记录能力。

核心功能：
  - test_get_user_queries_by_single_condition:
    验证按用户 ID、用户名或邮箱查询
  - test_get_user_rejects_invalid_conditions:
    验证查询条件必须且只能提供一个
  - test_list_users_builds_filtered_query:
    验证用户列表筛选、排序和分页
  - test_list_active_users_delegates_to_list_users:
    验证活跃用户列表复用通用查询
  - test_create_user:
    验证创建用户并加入数据库会话
  - test_update_user:
    验证用户资料更新和认证来源转换
  - test_replace_profile:
    验证完整替换用户资料并支持清空可选字段
  - test_update_password:
    验证密码哈希和修改时间更新
  - test_user_status_transitions:
    验证启用、停用、锁定和解锁
  - test_restore_user:
    验证恢复逻辑删除用户
  - test_record_login_success:
    验证登录成功状态记录
  - test_record_login_failure:
    验证登录失败次数递增
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

import datamind.db.repositories.user as user_module
from datamind.auth.enums import UserStatus
from datamind.db.models.users import User
from datamind.db.repositories.user import (
    UserPatch,
    UserRepository,
)


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)


def create_user(
        **overrides: Any,
) -> User:
    """创建用户测试对象."""
    values: dict[str, Any] = {
        "user_id": "usr_0123456789abcdef",
        "username": "alice",
        "password_hash": "argon2-password-hash",
        "display_name": "Alice",
        "email": "alice@example.com",
        "status": str(
            UserStatus.ACTIVE
        ),
        "created_by": "usr_admin",
    }
    values.update(
        overrides
    )

    user = User(
        **values
    )

    if "failed_login_count" not in overrides:
        user.failed_login_count = 0

    return user


def create_repository(
        *,
        scalar_result: User | None = None,
        list_result: list[User] | None = None,
) -> tuple[
    UserRepository,
    MagicMock,
    AsyncMock,
]:
    """创建用户仓储及异步会话替身."""
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

    repository = UserRepository(
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
    """将查询语句编译为 PostgreSQL SQL."""
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
                "user_id": "usr_0123456789abcdef",
            },
            (
                "users.user_id = "
                "'usr_0123456789abcdef'"
            ),
        ),
        (
            {
                "username": "alice",
            },
            "users.username = 'alice'",
        ),
        (
            {
                "email": "alice@example.com",
            },
            (
                "users.email = "
                "'alice@example.com'"
            ),
        ),
    ],
)
async def test_get_user_queries_by_single_condition(
        arguments: dict[str, str],
        expected_condition: str,
) -> None:
    """测试按用户 ID、用户名或邮箱查询."""
    expected_user = create_user()
    repository, _, execute = create_repository(
        scalar_result=expected_user
    )

    result = await repository.get_user(
        **arguments
    )

    assert result is expected_user
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
            "user_id": "usr_1",
            "username": "alice",
        },
        {
            "user_id": "usr_1",
            "email": "alice@example.com",
        },
        {
            "username": "alice",
            "email": "alice@example.com",
        },
        {
            "user_id": "usr_1",
            "username": "alice",
            "email": "alice@example.com",
        },
    ],
)
async def test_get_user_rejects_invalid_conditions(
        arguments: dict[str, str],
) -> None:
    """测试查询条件必须且只能提供一个."""
    repository, _, execute = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "user_id、username、email "
                "必须且只能提供一个"
            ),
    ):
        await repository.get_user(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_user_returns_none_when_not_found() -> None:
    """测试用户不存在时返回 None."""
    repository, _, _ = create_repository(
        scalar_result=None
    )

    result = await repository.get_user(
        username="missing-user"
    )

    assert result is None


@pytest.mark.asyncio
async def test_list_users_uses_default_order_and_limit() -> None:
    """测试用户列表默认排序和数量限制."""
    users = [
        create_user()
    ]
    repository, _, execute = create_repository(
        list_result=users
    )

    result = await repository.list_users()

    assert result == users
    execute.assert_awaited_once()

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert "ORDER BY users.created_at DESC" in sql
    assert "LIMIT 100" in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_users_builds_filtered_query() -> None:
    """测试用户列表筛选、排序和分页."""
    users = [
        create_user(
            status=str(
                UserStatus.DISABLED
            ),
        )
    ]
    repository, _, execute = create_repository(
        list_result=users
    )

    result = await repository.list_users(
        status=UserStatus.DISABLED,
        limit=25,
        offset=10,
    )

    assert result == users

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]
    sql = compile_statement(
        statement
    )

    assert "users.status = 'disabled'" in sql
    assert "ORDER BY users.created_at DESC" in sql
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_users_allows_unlimited_query() -> None:
    """测试用户列表允许不设置分页."""
    repository, _, execute = create_repository()

    await repository.list_users(
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
async def test_list_active_users_delegates_to_list_users(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试活跃用户列表复用通用查询."""
    users = [
        create_user()
    ]
    repository, _, _ = create_repository()
    list_users = AsyncMock(
        return_value=users
    )

    monkeypatch.setattr(
        repository,
        "list_users",
        list_users,
    )

    result = await repository.list_active_users(
        limit=50,
        offset=5,
    )

    assert result == users
    list_users.assert_awaited_once_with(
        status=UserStatus.ACTIVE,
        limit=50,
        offset=5,
    )


def test_user_patch_uses_slots_and_defaults() -> None:
    """测试用户更新结构默认值和 slots."""
    patch = UserPatch()

    assert patch.username is None
    assert patch.display_name is None
    assert patch.email is None
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_create_user() -> None:
    """测试创建用户并加入数据库会话."""
    repository, session, _ = create_repository()

    user = repository.create_user(
        user_id="usr_0123456789abcdef",
        username="alice",
        password_hash="argon2-password-hash",
        display_name="Alice",
        email="alice@example.com",
        status=UserStatus.ACTIVE,
        is_break_glass=True,
        created_by="usr_admin",
    )

    session.add.assert_called_once_with(
        user
    )
    assert user.user_id == "usr_0123456789abcdef"
    assert user.username == "alice"
    assert user.password_hash == "argon2-password-hash"
    assert user.display_name == "Alice"
    assert user.email == "alice@example.com"
    assert user.status == "active"
    assert user.is_break_glass is True
    assert user.created_by == "usr_admin"


def test_update_user() -> None:
    """测试用户资料更新."""
    repository, _, _ = create_repository()
    user = create_user()
    original_password_hash = user.password_hash
    original_status = user.status

    result = repository.update_user(
        user,
        patch=UserPatch(
            username="alice-new",
            display_name="Alice Chen",
            email="alice-new@example.com",
        ),
        updated_by="usr_admin",
    )

    assert result is user
    assert user.username == "alice-new"
    assert user.display_name == "Alice Chen"
    assert user.email == "alice-new@example.com"
    assert user.password_hash == original_password_hash
    assert user.status == original_status
    assert user.updated_by == "usr_admin"


def test_update_user_ignores_none_fields() -> None:
    """测试用户更新忽略值为 None 的字段."""
    repository, _, _ = create_repository()
    user = create_user(
        updated_by="usr_original"
    )

    repository.update_user(
        user,
        patch=UserPatch(
            display_name="Alice Chen",
        ),
    )

    assert user.username == "alice"
    assert user.display_name == "Alice Chen"
    assert user.email == "alice@example.com"
    assert user.updated_by == "usr_original"


def test_replace_profile() -> None:
    """测试完整替换用户资料并支持清空可选字段."""
    repository, _, _ = create_repository()
    user = create_user()

    result = repository.replace_profile(
        user,
        username="alice-new",
        display_name=None,
        email=None,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.username == "alice-new"
    assert getattr(
        user,
        "display_name",
    ) is None
    assert getattr(
        user,
        "email",
    ) is None
    assert user.updated_by == "usr_admin"


def test_update_password_with_explicit_time() -> None:
    """测试使用指定时间更新密码哈希."""
    repository, _, _ = create_repository()
    user = create_user()

    result = repository.update_password(
        user,
        password_hash="new-password-hash",
        changed_at=CURRENT_TIME,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.password_hash == "new-password-hash"
    assert user.password_changed_at == CURRENT_TIME
    assert user.updated_by == "usr_admin"


def test_update_password_uses_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未指定时间时使用当前 UTC 时间."""
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
    user = create_user()

    monkeypatch.setitem(
        vars(user_module),
        "datetime",
        FrozenDateTime,
    )

    repository.update_password(
        user,
        password_hash="new-password-hash",
    )

    assert user.password_changed_at == CURRENT_TIME


# noinspection PyUnreachableCode
def test_activate_user() -> None:
    """测试启用用户并清除锁定状态."""
    repository, _, _ = create_repository()
    user = create_user(
        status=str(
            UserStatus.LOCKED
        ),
        failed_login_count=5,
        locked_until=CURRENT_TIME,
    )

    result = repository.activate_user(
        user,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.status == "active"
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.updated_by == "usr_admin"


# noinspection PyUnreachableCode
def test_disable_user() -> None:
    """测试停用用户并清除临时锁定时间."""
    repository, _, _ = create_repository()
    user = create_user(
        failed_login_count=3,
        locked_until=CURRENT_TIME,
    )

    result = repository.disable_user(
        user,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.status == "disabled"
    assert user.failed_login_count == 3
    assert user.locked_until is None
    assert user.updated_by == "usr_admin"


# noinspection PyUnreachableCode
def test_mark_deleted_user() -> None:
    """测试逻辑删除用户并保留身份记录."""
    repository, _, _ = create_repository()
    user = create_user(
        status=str(
            UserStatus.ACTIVE
        ),
        locked_until=CURRENT_TIME,
        deleted_at=None,
    )

    result = repository.mark_deleted(
        user,
        deleted_by="usr_admin",
        deletion_reason="员工离职",
        deleted_at=CURRENT_TIME,
    )

    assert result is user
    assert user.status == "disabled"
    assert user.locked_until is None
    assert user.deleted_at == CURRENT_TIME
    assert user.deleted_by == "usr_admin"
    assert user.deletion_reason == "员工离职"
    assert user.updated_by == "usr_admin"


# noinspection PyUnreachableCode
def test_restore_user() -> None:
    """测试恢复逻辑删除用户."""
    repository, _, _ = create_repository()
    user = create_user(
        status=str(
            UserStatus.DISABLED
        ),
        failed_login_count=5,
        locked_until=CURRENT_TIME,
        deleted_at=CURRENT_TIME,
        deleted_by="usr_admin",
        deletion_reason="员工离职",
    )

    result = repository.restore_user(
        user,
        restored_at=CURRENT_TIME,
        restored_by="usr_admin",
    )

    assert result is user
    assert user.status == "active"
    assert user.created_at == CURRENT_TIME
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.deleted_at is None
    assert user.deleted_by is None
    assert user.deletion_reason is None
    assert user.updated_by == "usr_admin"


def test_lock_user() -> None:
    """测试锁定用户."""
    repository, _, _ = create_repository()
    user = create_user()

    result = repository.lock_user(
        user,
        locked_until=CURRENT_TIME,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.status == "locked"
    assert user.locked_until == CURRENT_TIME
    assert user.updated_by == "usr_admin"


# noinspection PyUnreachableCode
def test_unlock_user() -> None:
    """测试解锁用户并清除失败次数."""
    repository, _, _ = create_repository()
    user = create_user(
        status=str(
            UserStatus.LOCKED
        ),
        failed_login_count=5,
        locked_until=CURRENT_TIME,
    )

    result = repository.unlock_user(
        user,
        updated_by="usr_admin",
    )

    assert result is user
    assert user.status == "active"
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.updated_by == "usr_admin"


def test_status_update_preserves_existing_updated_by() -> None:
    """测试未提供更新人时保留原更新人."""
    repository, _, _ = create_repository()
    user = create_user(
        updated_by="usr_original"
    )

    repository.lock_user(
        user
    )

    assert user.updated_by == "usr_original"


def test_record_login_success_with_explicit_time() -> None:
    """测试记录登录成功并清除失败次数."""
    repository, _, _ = create_repository()
    user = create_user(
        failed_login_count=4
    )

    result = repository.record_login_success(
        user,
        logged_in_at=CURRENT_TIME,
    )

    assert result is user
    assert user.failed_login_count == 0
    assert user.last_login_at == CURRENT_TIME


def test_record_login_success_uses_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未指定登录时间时使用当前 UTC 时间."""
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
    user = create_user(
        failed_login_count=2
    )

    monkeypatch.setitem(
        vars(user_module),
        "datetime",
        FrozenDateTime,
    )

    repository.record_login_success(
        user
    )

    assert user.failed_login_count == 0
    assert user.last_login_at == CURRENT_TIME


def test_record_login_failure() -> None:
    """测试登录失败次数递增."""
    repository, _, _ = create_repository()
    user = create_user(
        failed_login_count=2
    )

    result = repository.record_login_failure(
        user
    )

    assert result is user
    assert user.failed_login_count == 3
