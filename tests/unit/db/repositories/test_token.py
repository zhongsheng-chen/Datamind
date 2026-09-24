"""认证令牌仓储测试.

验证刷新令牌查询、列表筛选、创建、使用时间记录、
单令牌撤销和用户全部令牌撤销能力。

核心功能：
  - test_get_token_queries_by_single_condition:
    验证按令牌 ID 或令牌哈希查询
  - test_get_token_rejects_invalid_conditions:
    验证查询条件必须且只能提供一个
  - test_get_token_can_lock_record_for_update:
    验证刷新令牌轮换查询可以锁定记录
  - test_list_tokens_builds_query:
    验证令牌列表筛选、排序和分页
  - test_list_active_tokens:
    验证有效令牌查询
  - test_create_token:
    验证创建刷新令牌记录
  - test_record_token_use:
    验证记录刷新令牌使用时间
  - test_revoke_token:
    验证撤销刷新令牌
  - test_revoke_token_is_idempotent:
    验证重复撤销不会覆盖原撤销信息
  - test_revoke_user_tokens:
    验证撤销用户的全部有效刷新令牌
  - test_token_time_operations_use_current_utc_time:
    验证默认时间统一使用当前 UTC 时间
"""

from datetime import (
    datetime,
    timedelta,
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

import datamind.db.repositories.token as token_module
from datamind.auth.enums import TokenStatus
from datamind.db.models.tokens import Token
from datamind.db.repositories.token import TokenRepository


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)
EXPIRES_AT = (
    CURRENT_TIME
    + timedelta(
        days=7
    )
)
TOKEN_HASH = (
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
)


def create_token(
        **overrides: Any,
) -> Token:
    """创建刷新令牌测试对象."""
    values: dict[str, Any] = {
        "token_id": "tok_0123456789abcdef",
        "user_id": "usr_0123456789abcdef",
        "token_hash": TOKEN_HASH,
        "status": str(
            TokenStatus.ACTIVE
        ),
        "expires_at": EXPIRES_AT,
        "ip": "192.168.1.100",
        "hostname": "client",
        "user_agent": "Datamind CLI",
    }
    values.update(
        overrides
    )

    return Token(
        **values
    )


def create_repository(
        *,
        scalar_result: Token | None = None,
        list_result: list[Token] | None = None,
) -> tuple[
    TokenRepository,
    MagicMock,
    AsyncMock,
]:
    """创建令牌仓储及异步会话替身."""
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

    repository = TokenRepository(
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


def get_executed_statement(
        execute: AsyncMock,
) -> Select[Any]:
    """获取异步会话最近执行的查询语句."""
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
                "token_id": "tok_0123456789abcdef",
            },
            (
                "tokens.token_id = "
                "'tok_0123456789abcdef'"
            ),
        ),
        (
            {
                "token_hash": TOKEN_HASH,
            },
            (
                "tokens.token_hash = "
                f"'{TOKEN_HASH}'"
            ),
        ),
    ],
)
async def test_get_token_queries_by_single_condition(
        arguments: dict[str, str],
        expected_condition: str,
) -> None:
    """测试按令牌 ID 或令牌哈希查询."""
    expected_token = create_token()
    repository, _, execute = create_repository(
        scalar_result=expected_token
    )

    result = await repository.get_token(
        **arguments
    )

    assert result is expected_token
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert expected_condition in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {
            "token_id": "tok_1",
            "token_hash": TOKEN_HASH,
        },
    ],
)
async def test_get_token_rejects_invalid_conditions(
        arguments: dict[str, str],
) -> None:
    """测试查询条件必须且只能提供一个."""
    repository, _, execute = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "token_id、token_hash "
                "必须且只能提供一个"
            ),
    ):
        await repository.get_token(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_token_returns_none_when_not_found() -> None:
    """测试刷新令牌不存在时返回 None."""
    repository, _, _ = create_repository(
        scalar_result=None
    )

    result = await repository.get_token(
        token_id="tok_missing"
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_token_can_lock_record_for_update() -> None:
    """测试刷新令牌轮换查询可以锁定记录."""
    repository, _, execute = create_repository(
        scalar_result=create_token()
    )

    await repository.get_token(
        token_hash=TOKEN_HASH,
        for_update=True,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert sql.endswith(" FOR UPDATE")


@pytest.mark.asyncio
async def test_list_tokens_uses_default_order_and_limit() -> None:
    """测试令牌列表默认排序和数量限制."""
    tokens = [
        create_token()
    ]
    repository, _, execute = create_repository(
        list_result=tokens
    )

    result = await repository.list_tokens()

    assert result == tokens
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY tokens.created_at DESC"
        in sql
    )
    assert "LIMIT 100" in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_tokens_builds_filtered_query() -> None:
    """测试令牌列表筛选、排序和分页."""
    expires_before = (
        CURRENT_TIME
        + timedelta(
            days=10
        )
    )
    expires_after = (
        CURRENT_TIME
        - timedelta(
            days=1
        )
    )
    tokens = [
        create_token(
            status=str(
                TokenStatus.REVOKED
            ),
            revoked_at=CURRENT_TIME,
        )
    ]
    repository, _, execute = create_repository(
        list_result=tokens
    )

    result = await repository.list_tokens(
        user_id="usr_0123456789abcdef",
        status=TokenStatus.REVOKED,
        expires_before=expires_before,
        expires_after=expires_after,
        limit=25,
        offset=10,
    )

    assert result == tokens

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "tokens.user_id = "
        "'usr_0123456789abcdef'"
        in sql
    )
    assert "tokens.status = 'revoked'" in sql
    assert "tokens.expires_at <=" in sql
    assert "tokens.expires_at >" in sql
    assert (
        "ORDER BY tokens.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_tokens_uses_strict_expires_after() -> None:
    """测试过期时间下限使用严格大于条件."""
    repository, _, execute = create_repository()

    await repository.list_tokens(
        expires_after=CURRENT_TIME,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "tokens.expires_at >" in sql
    assert "tokens.expires_at >=" not in sql


@pytest.mark.asyncio
async def test_list_tokens_allows_unlimited_query() -> None:
    """测试令牌列表允许不设置分页."""
    repository, _, execute = create_repository()

    await repository.list_tokens(
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
async def test_list_active_tokens_delegates_to_list_tokens(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效令牌查询复用通用查询."""
    tokens = [
        create_token()
    ]
    repository, _, _ = create_repository()
    list_tokens = AsyncMock(
        return_value=tokens
    )

    monkeypatch.setattr(
        repository,
        "list_tokens",
        list_tokens,
    )

    result = await repository.list_active_tokens(
        user_id="usr_0123456789abcdef",
        current_time=CURRENT_TIME,
        limit=50,
        offset=5,
    )

    assert result == tokens
    list_tokens.assert_awaited_once_with(
        user_id="usr_0123456789abcdef",
        status=TokenStatus.ACTIVE,
        expires_after=CURRENT_TIME,
        limit=50,
        offset=5,
    )


@pytest.mark.asyncio
async def test_list_active_tokens_uses_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效令牌查询默认使用当前 UTC 时间."""
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
    list_tokens = AsyncMock(
        return_value=[]
    )

    monkeypatch.setitem(
        vars(token_module),
        "datetime",
        FrozenDateTime,
    )
    monkeypatch.setattr(
        repository,
        "list_tokens",
        list_tokens,
    )

    await repository.list_active_tokens(
        user_id="usr_0123456789abcdef"
    )

    list_tokens.assert_awaited_once_with(
        user_id="usr_0123456789abcdef",
        status=TokenStatus.ACTIVE,
        expires_after=CURRENT_TIME,
        limit=100,
        offset=None,
    )


# noinspection PyUnreachableCode
def test_create_token_uses_defaults() -> None:
    """测试创建默认有效刷新令牌."""
    repository, session, _ = create_repository()

    token = repository.create_token(
        token_id="tok_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        expires_at=EXPIRES_AT,
    )

    session.add.assert_called_once_with(
        token
    )
    assert token.token_id == (
        "tok_0123456789abcdef"
    )
    assert token.user_id == (
        "usr_0123456789abcdef"
    )
    assert token.token_hash == TOKEN_HASH
    assert token.status == "active"
    assert token.expires_at == EXPIRES_AT
    assert token.ip is None
    assert token.hostname is None
    assert token.user_agent is None


def test_create_token_with_client_information() -> None:
    """测试创建包含客户端信息的刷新令牌."""
    repository, session, _ = create_repository()

    token = repository.create_token(
        token_id="tok_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        expires_at=EXPIRES_AT,
        status=TokenStatus.ACTIVE,
        ip="192.168.1.100",
        hostname="client",
        user_agent="Datamind CLI",
    )

    session.add.assert_called_once_with(
        token
    )
    assert token.ip == "192.168.1.100"
    assert token.hostname == "client"
    assert token.user_agent == "Datamind CLI"


def test_record_token_use_with_explicit_time() -> None:
    """测试使用指定时间记录刷新令牌使用时间."""
    repository, _, _ = create_repository()
    token = create_token()

    result = repository.record_token_use(
        token,
        used_at=CURRENT_TIME,
    )

    assert result is token
    assert token.last_used_at == CURRENT_TIME


def test_record_token_use_uses_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录使用时间默认使用当前 UTC 时间."""
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
    token = create_token()

    monkeypatch.setitem(
        vars(token_module),
        "datetime",
        FrozenDateTime,
    )

    repository.record_token_use(
        token
    )

    assert token.last_used_at == CURRENT_TIME


def test_revoke_token_with_explicit_values() -> None:
    """测试使用指定信息撤销刷新令牌."""
    repository, _, _ = create_repository()
    token = create_token()

    result = repository.revoke_token(
        token,
        revoked_by="usr_admin",
        revoke_reason="logout",
        revoked_at=CURRENT_TIME,
    )

    assert result is token
    assert token.status == "revoked"
    assert token.revoked_by == "usr_admin"
    assert token.revoke_reason == "logout"
    assert token.revoked_at == CURRENT_TIME


# noinspection PyUnreachableCode
def test_revoke_token_allows_optional_metadata() -> None:
    """测试撤销令牌时允许不提供撤销人和原因."""
    repository, _, _ = create_repository()
    token = create_token()

    repository.revoke_token(
        token,
        revoked_at=CURRENT_TIME,
    )

    assert token.status == "revoked"
    assert token.revoked_by is None
    assert token.revoke_reason is None
    assert token.revoked_at == CURRENT_TIME


def test_revoke_token_is_idempotent() -> None:
    """测试重复撤销不会覆盖原撤销信息."""
    original_revoked_at = (
        CURRENT_TIME
        - timedelta(
            hours=1
        )
    )
    token = create_token(
        status=str(
            TokenStatus.REVOKED
        ),
        revoked_by="usr_original",
        revoke_reason="original_reason",
        revoked_at=original_revoked_at,
    )
    repository, _, _ = create_repository()

    result = repository.revoke_token(
        token,
        revoked_by="usr_changed",
        revoke_reason="changed_reason",
        revoked_at=CURRENT_TIME,
    )

    assert result is token
    assert token.revoked_by == "usr_original"
    assert token.revoke_reason == "original_reason"
    assert token.revoked_at == original_revoked_at


def test_revoke_token_uses_current_utc_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试撤销令牌默认使用当前 UTC 时间."""
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
    token = create_token()

    monkeypatch.setitem(
        vars(token_module),
        "datetime",
        FrozenDateTime,
    )

    repository.revoke_token(
        token
    )

    assert token.revoked_at == CURRENT_TIME


@pytest.mark.asyncio
async def test_revoke_user_tokens(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试撤销用户的全部有效刷新令牌."""
    tokens = [
        create_token(
            token_id="tok_1",
        ),
        create_token(
            token_id="tok_2",
            token_hash=(
                "abcdef0123456789"
                "abcdef0123456789"
                "abcdef0123456789"
                "abcdef0123456789"
            ),
        ),
    ]
    repository, _, _ = create_repository()
    list_tokens = AsyncMock(
        return_value=tokens
    )
    revoke_token = MagicMock(
        side_effect=(
            lambda token_record, **kwargs: token_record
        )
    )

    monkeypatch.setattr(
        repository,
        "list_tokens",
        list_tokens,
    )
    monkeypatch.setattr(
        repository,
        "revoke_token",
        revoke_token,
    )

    result = await repository.revoke_user_tokens(
        user_id="usr_0123456789abcdef",
        revoked_by="usr_admin",
        revoke_reason="user_disabled",
        revoked_at=CURRENT_TIME,
    )

    assert result == tokens
    list_tokens.assert_awaited_once_with(
        user_id="usr_0123456789abcdef",
        status=TokenStatus.ACTIVE,
        limit=None,
    )
    assert revoke_token.call_count == 2

    for token in tokens:
        revoke_token.assert_any_call(
            token,
            revoked_by="usr_admin",
            revoke_reason="user_disabled",
            revoked_at=CURRENT_TIME,
        )


@pytest.mark.asyncio
async def test_revoke_user_tokens_returns_empty_list(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试用户没有有效令牌时返回空列表."""
    repository, _, _ = create_repository()
    list_tokens = AsyncMock(
        return_value=[]
    )
    revoke_token = MagicMock()

    monkeypatch.setattr(
        repository,
        "list_tokens",
        list_tokens,
    )
    monkeypatch.setattr(
        repository,
        "revoke_token",
        revoke_token,
    )

    result = await repository.revoke_user_tokens(
        user_id="usr_0123456789abcdef",
        revoked_at=CURRENT_TIME,
    )

    assert result == []
    revoke_token.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_user_tokens_uses_single_current_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量撤销默认使用同一个当前 UTC 时间."""
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

    tokens = [
        create_token(
            token_id="tok_1",
        ),
        create_token(
            token_id="tok_2",
        ),
    ]
    repository, _, _ = create_repository()
    list_tokens = AsyncMock(
        return_value=tokens
    )
    revoke_token = MagicMock(
        side_effect=(
            lambda token_record, **kwargs: token_record
        )
    )

    monkeypatch.setitem(
        vars(token_module),
        "datetime",
        FrozenDateTime,
    )
    monkeypatch.setattr(
        repository,
        "list_tokens",
        list_tokens,
    )
    monkeypatch.setattr(
        repository,
        "revoke_token",
        revoke_token,
    )

    await repository.revoke_user_tokens(
        user_id="usr_0123456789abcdef"
    )

    for token in tokens:
        revoke_token.assert_any_call(
            token,
            revoked_by=None,
            revoke_reason=None,
            revoked_at=CURRENT_TIME,
        )
