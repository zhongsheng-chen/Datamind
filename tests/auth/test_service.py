# tests/auth/test_service.py

"""认证服务测试

验证 LOCAL 登录、网络限制、令牌生命周期和应急账户行为。

核心功能：
  - test_login_issues_tokens:
    验证本地登录签发访问令牌和刷新令牌
  - test_login_enforces_allowed_networks:
    验证本地登录限制客户端网段
  - test_login_matches_user_by_email:
    验证用户名未匹配时使用邮箱匹配本地用户
  - test_break_glass_login_issues_access_token_only:
    验证应急账户只签发短期访问令牌
  - test_login_validates_user_status:
    验证登录拒绝已停用用户
  - test_refresh_rotates_refresh_token:
    验证刷新令牌成功轮换
  - test_refresh_rejects_invalid_token_state:
    验证刷新令牌拒绝无效状态
  - test_refresh_rejects_break_glass_user:
    验证应急账户不能使用刷新令牌
  - test_logout_is_idempotent:
    验证退出登录撤销令牌且重复调用保持幂等
  - test_authenticate_access_token_returns_user:
    验证访问令牌认证返回本地用户
  - test_authenticate_access_token_rejects_invalid_token:
    验证访问令牌认证拒绝无效令牌"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
    call,
)

import pytest

import datamind.auth.service as service_module
from datamind.auth.enums import (
    TokenStatus,
    UserStatus,
)
from datamind.auth.errors import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    UserDisabledError,
)
from datamind.auth.providers import (
    BaseAuthProvider,
    PasswordCredentials,
    ProviderIdentity,
)
from datamind.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from datamind.auth.service import AuthService


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)


class FakeAuthProvider(BaseAuthProvider):
    """记录调用的本地认证提供方"""

    def __init__(
            self,
            *,
            identity: ProviderIdentity | None = None,
            error: Exception | None = None,
    ) -> None:
        self.identity = (
            identity
            or ProviderIdentity(
                subject="usr_test",
                username="alice",
                email="alice@example.com",
            )
        )
        self.error = error
        self.calls: list[
            tuple[
                PasswordCredentials,
                datetime | None,
            ]
        ] = []

    async def authenticate(
            self,
            credentials: PasswordCredentials,
            *,
            current_time: datetime | None = None,
    ) -> ProviderIdentity:
        """记录调用并返回测试身份"""
        self.calls.append(
            (
                credentials,
                current_time,
            )
        )

        if self.error is not None:
            raise self.error

        return self.identity


def create_user(
        **overrides: Any,
) -> SimpleNamespace:
    """创建测试用户"""
    values: dict[str, Any] = {
        "user_id": "usr_test",
        "username": "alice",
        "display_name": "Alice",
        "email": "alice@example.com",
        "status": str(
            UserStatus.ACTIVE
        ),
        "failed_login_count": 0,
        "locked_until": None,
        "is_break_glass": False,
    }
    values.update(
        overrides
    )

    return SimpleNamespace(
        **values
    )


def create_token_record(
        **overrides: Any,
) -> SimpleNamespace:
    """创建测试刷新令牌记录"""
    values: dict[str, Any] = {
        "token_id": "tok_old",
        "user_id": "usr_test",
        "token_hash": "old-token-hash",
        "status": str(
            TokenStatus.ACTIVE
        ),
        "expires_at": CURRENT_TIME + timedelta(days=1),
        "ip": "10.1.2.3",
        "hostname": "client",
        "user_agent": "datamind-cli",
    }
    values.update(
        overrides
    )

    return SimpleNamespace(
        **values
    )


def create_service(
        *,
        provider: BaseAuthProvider | None = None,
        allowed_networks: tuple[str, ...] = (),
        break_glass_minutes: int = 15,
) -> tuple[
    AuthService,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    """创建认证服务及仓储替身"""
    user_repo = MagicMock()
    user_repo.get_user = AsyncMock()
    role_repo = MagicMock()
    role_repo.get_role = AsyncMock()
    grant_repo = MagicMock()
    grant_repo.list_active_grants = AsyncMock(
        return_value=[]
    )
    token_repo = MagicMock()
    token_repo.get_token = AsyncMock()

    service = AuthService(
        user_repo=user_repo,
        role_repo=role_repo,
        grant_repo=grant_repo,
        token_repo=token_repo,
        secret_key="secure-test-secret",
        provider=provider,
        local_allowed_networks=allowed_networks,
        break_glass_access_token_expires_minutes=(
            break_glass_minutes
        ),
    )

    return (
        service,
        user_repo,
        role_repo,
        grant_repo,
        token_repo,
    )


def install_token_functions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """替换令牌函数"""
    monkeypatch.setitem(
        vars(service_module),
        "create_access_token",
        lambda **_kwargs: "access-token",
    )
    monkeypatch.setitem(
        vars(service_module),
        "generate_refresh_token",
        lambda: "new-refresh-token",
    )
    monkeypatch.setitem(
        vars(service_module),
        "hash_refresh_token",
        lambda _token: "token-hash",
    )
    monkeypatch.setitem(
        vars(service_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_test",
    )


@pytest.mark.asyncio
async def test_login_issues_tokens(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证本地登录签发访问令牌和刷新令牌"""
    user = create_user()
    provider = FakeAuthProvider()
    service, user_repo, _, _, token_repo = create_service(
        provider=provider
    )
    user_repo.get_user.return_value = user
    install_token_functions(
        monkeypatch
    )

    response = await service.login(
        LoginRequest.model_validate({
            "username": "alice",
            "password": "P@ssw1rd",
        }),
        ip="10.1.2.3",
        hostname="client",
        user_agent="datamind-cli",
        current_time=CURRENT_TIME,
    )

    assert response == TokenResponse(
        access_token="access-token",
        refresh_token="new-refresh-token",
        expires_in=1800,
    )
    credentials, authenticated_at = provider.calls[0]
    assert credentials.username == "alice"
    assert credentials.password == "P@ssw1rd"
    assert authenticated_at == CURRENT_TIME
    token_repo.create_token.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ip", "message"),
    [
        (None, "LOCAL 认证缺少客户端 IP"),
        ("invalid", "LOCAL 认证客户端 IP 无效"),
        ("192.168.1.10", "当前网络不允许使用 LOCAL 认证"),
    ],
)
async def test_login_enforces_allowed_networks(
        ip: str | None,
        message: str,
) -> None:
    """验证本地登录限制客户端网段"""
    provider = FakeAuthProvider()
    service, *_ = create_service(
        provider=provider,
        allowed_networks=(
            "10.0.0.0/8",
        ),
    )

    with pytest.raises(
            InvalidCredentialsError,
            match=message,
    ):
        await service.login(
            LoginRequest.model_validate({
                "username": "alice",
                "password": "password",
            }),
            ip=ip,
            current_time=CURRENT_TIME,
        )

    assert provider.calls == []


@pytest.mark.asyncio
async def test_login_matches_user_by_email(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证用户名未匹配时使用邮箱匹配本地用户"""
    user = create_user()
    provider = FakeAuthProvider(
        identity=ProviderIdentity(
            subject="usr_external",
            username="unknown",
            email="alice@example.com",
        )
    )
    service, user_repo, *_ = create_service(
        provider=provider
    )
    user_repo.get_user.side_effect = [
        None,
        user,
    ]
    install_token_functions(
        monkeypatch
    )

    await service.login(
        LoginRequest.model_validate({
            "username": "alice",
            "password": "password",
        }),
        current_time=CURRENT_TIME,
    )

    assert user_repo.get_user.await_args_list == [
        call(
            username="unknown"
        ),
        call(
            email="alice@example.com"
        ),
    ]


@pytest.mark.asyncio
async def test_break_glass_login_issues_access_token_only(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证应急账户只签发短期访问令牌"""
    user = create_user(
        is_break_glass=True
    )
    service, user_repo, _, _, token_repo = create_service(
        provider=FakeAuthProvider(),
        break_glass_minutes=10,
    )
    user_repo.get_user.return_value = user
    install_token_functions(
        monkeypatch
    )

    response = await service.login(
        LoginRequest.model_validate({
            "username": "alice",
            "password": "password",
        }),
        current_time=CURRENT_TIME,
    )

    assert response.refresh_token is None
    assert response.expires_in == 600
    token_repo.create_token.assert_not_called()


@pytest.mark.asyncio
async def test_login_validates_user_status() -> None:
    """验证登录拒绝已停用用户"""
    service, user_repo, *_ = create_service(
        provider=FakeAuthProvider()
    )
    user_repo.get_user.return_value = create_user(
        status=str(
            UserStatus.DISABLED
        )
    )

    with pytest.raises(UserDisabledError):
        await service.login(
            LoginRequest.model_validate({
                "username": "alice",
                "password": "password",
            }),
            current_time=CURRENT_TIME,
        )


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证刷新令牌成功轮换"""
    token = create_token_record()
    user = create_user()
    service, user_repo, _, _, token_repo = create_service()
    token_repo.get_token.return_value = token
    user_repo.get_user.return_value = user
    install_token_functions(
        monkeypatch
    )
    monkeypatch.setitem(
        vars(service_module),
        "verify_refresh_token",
        lambda **_kwargs: True,
    )

    response = await service.refresh(
        RefreshTokenRequest.model_validate({
            "refresh_token": "old-refresh-token",
        }),
        current_time=CURRENT_TIME,
    )

    assert response.refresh_token == "new-refresh-token"
    token_repo.record_token_use.assert_called_once_with(
        token,
        used_at=CURRENT_TIME,
    )
    token_repo.revoke_token.assert_called_once_with(
        token,
        revoked_by=user.user_id,
        revoke_reason="refresh_token_rotated",
        revoked_at=CURRENT_TIME,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token", "error_type"),
    [
        (None, InvalidRefreshTokenError),
        (
            create_token_record(
                status=str(
                    TokenStatus.REVOKED
                )
            ),
            RefreshTokenRevokedError,
        ),
        (
            create_token_record(
                expires_at=CURRENT_TIME
            ),
            RefreshTokenExpiredError,
        ),
    ],
)
async def test_refresh_rejects_invalid_token_state(
        monkeypatch: pytest.MonkeyPatch,
        token: SimpleNamespace | None,
        error_type: type[Exception],
) -> None:
    """验证刷新令牌拒绝无效状态"""
    service, _, _, _, token_repo = create_service()
    token_repo.get_token.return_value = token
    monkeypatch.setitem(
        vars(service_module),
        "hash_refresh_token",
        lambda _token: "token-hash",
    )
    monkeypatch.setitem(
        vars(service_module),
        "verify_refresh_token",
        lambda **_kwargs: True,
    )

    with pytest.raises(error_type):
        await service.refresh(
            RefreshTokenRequest.model_validate({
                "refresh_token": "refresh-token",
            }),
            current_time=CURRENT_TIME,
        )


@pytest.mark.asyncio
async def test_refresh_rejects_break_glass_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证应急账户不能使用刷新令牌"""
    token = create_token_record()
    service, user_repo, _, _, token_repo = create_service()
    token_repo.get_token.return_value = token
    user_repo.get_user.return_value = create_user(
        is_break_glass=True
    )
    monkeypatch.setitem(
        vars(service_module),
        "hash_refresh_token",
        lambda _token: "token-hash",
    )
    monkeypatch.setitem(
        vars(service_module),
        "verify_refresh_token",
        lambda **_kwargs: True,
    )

    with pytest.raises(
            InvalidRefreshTokenError,
            match="应急账户不允许使用刷新令牌",
    ):
        await service.refresh(
            RefreshTokenRequest.model_validate({
                "refresh_token": "refresh-token",
            }),
            current_time=CURRENT_TIME,
        )

    token_repo.revoke_token.assert_called_once()


@pytest.mark.asyncio
async def test_logout_is_idempotent(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证退出登录撤销令牌且重复调用保持幂等"""
    token = create_token_record()
    service, _, _, _, token_repo = create_service()
    token_repo.get_token.side_effect = [
        token,
        None,
    ]
    monkeypatch.setitem(
        vars(service_module),
        "hash_refresh_token",
        lambda _token: "token-hash",
    )
    request = LogoutRequest.model_validate({
        "refresh_token": "refresh-token",
    })

    assert await service.logout(
        request,
        current_time=CURRENT_TIME,
    ) is True
    assert await service.logout(
        request,
        current_time=CURRENT_TIME,
    ) is False
    token_repo.revoke_token.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_access_token_returns_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证访问令牌认证返回本地用户"""
    user = create_user()
    service, user_repo, *_ = create_service()
    user_repo.get_user.return_value = user
    monkeypatch.setitem(
        vars(service_module),
        "decode_access_token",
        lambda **_kwargs: {
            "sub": user.user_id,
            "type": "access",
            "iat": int(CURRENT_TIME.timestamp()),
            "exp": int(
                (
                    CURRENT_TIME
                    + timedelta(minutes=30)
                ).timestamp()
            ),
        },
    )

    authenticated = await service.authenticate_access_token(
        "access-token",
        current_time=CURRENT_TIME,
    )

    assert authenticated.user_id == user.user_id
    assert authenticated.username == user.username
    assert authenticated.status == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_authenticate_access_token_rejects_invalid_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证访问令牌认证拒绝无效令牌"""
    service, *_ = create_service()
    monkeypatch.setitem(
        vars(service_module),
        "decode_access_token",
        lambda **_kwargs: None,
    )

    with pytest.raises(InvalidAccessTokenError):
        await service.authenticate_access_token(
            "invalid-token",
            current_time=CURRENT_TIME,
        )
