"""运行时认证接口测试

验证登录、令牌续期、退出和认证错误响应行为。

核心功能：
  - test_auth_endpoints_use_top_level_request_schemas:
    验证认证端点使用顶层请求数据结构
  - test_login_returns_tokens_without_cache:
    验证本地登录签发不缓存的令牌响应
  - test_login_hides_authentication_failure:
    验证登录失败不暴露账户状态
  - test_refresh_rotates_tokens:
    验证刷新接口轮换访问令牌和刷新令牌
  - test_refresh_hides_invalid_token_details:
    验证刷新失败返回统一认证错误
  - test_logout_is_idempotent:
    验证退出接口幂等撤销刷新令牌
  - test_login_reports_unavailable_auth_service:
    验证认证配置不可用时返回 HTTP 503
"""

from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest
from pydantic import SecretStr

from datamind.auth.errors import AuthError, InvalidCredentialsError, InvalidRefreshTokenError
from datamind.auth.schemas import TokenResponse


def test_auth_endpoints_use_top_level_request_schemas(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证端点使用顶层请求数据结构"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    apis = (
        service_module
        .DatamindRuntimeService
        .apis
    )

    assert apis["login"].route == "/auth/login"
    assert set(
        apis["login"].input_spec.model_fields
    ) == {
        "username",
        "password",
    }
    assert apis["refresh"].route == "/auth/refresh"
    assert set(
        apis["refresh"].input_spec.model_fields
    ) == {
        "refresh_token",
    }
    assert apis["logout"].route == "/auth/logout"
    assert set(
        apis["logout"].input_spec.model_fields
    ) == {
        "refresh_token",
    }


@pytest.mark.asyncio
async def test_login_returns_tokens_without_cache(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地登录签发不缓存的令牌响应"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=1800,
        )
    )
    runtime_server.install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("secret"),
        ctx=context,
    )

    assert result == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "expires_in": 1800,
    }
    assert context.response.status_code == 200
    assert context.response.headers[
        "cache-control"
    ] == "no-store"
    assert context.response.headers[
        "pragma"
    ] == "no-cache"
    awaited_call = auth_service.login.await_args
    assert awaited_call is not None
    login_request = awaited_call.args[0]
    assert login_request.username == "alice"
    assert (
        login_request.password.get_secret_value()
        == "secret"
    )
    assert awaited_call.kwargs == {
        "ip": "127.0.0.1",
        "user_agent": "pytest",
    }


@pytest.mark.asyncio
async def test_login_hides_authentication_failure(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录失败不暴露账户状态"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        side_effect=InvalidCredentialsError()
    )
    runtime_server.install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("invalid"),
        ctx=context,
    )

    assert result == {
        "error": "用户名或密码错误"
    }
    assert context.response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新接口轮换访问令牌和刷新令牌"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        return_value=TokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=1800,
        )
    )
    runtime_server.install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.refresh(
        refresh_token=SecretStr("refresh-token"),
        ctx=context,
    )

    assert result["access_token"] == "new-access-token"
    assert result["refresh_token"] == "new-refresh-token"
    awaited_call = auth_service.refresh.await_args
    assert awaited_call is not None
    refresh_request = awaited_call.args[0]
    assert (
        refresh_request.refresh_token.get_secret_value()
        == "refresh-token"
    )


@pytest.mark.asyncio
async def test_refresh_hides_invalid_token_details(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新失败返回统一认证错误"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        side_effect=InvalidRefreshTokenError()
    )
    runtime_server.install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.refresh(
        refresh_token=SecretStr("invalid"),
        ctx=context,
    )

    assert result == {
        "error": "刷新令牌无效或已失效"
    }
    assert context.response.status_code == 401


@pytest.mark.asyncio
async def test_logout_is_idempotent(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退出接口幂等撤销刷新令牌"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.logout = AsyncMock(
        return_value=False
    )
    runtime_server.install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.logout(
        refresh_token=SecretStr("refresh-token"),
        ctx=context,
    )

    assert result == {}
    assert context.response.status_code == 204
    auth_service.logout.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_reports_unavailable_auth_service(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证配置不可用时返回 HTTP 503"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    runtime_service = runtime_server.create_service(
        service_module
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "UnitOfWork",
        runtime_server.FakeUnitOfWork,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "create_auth_service",
        MagicMock(
            side_effect=AuthError()
        ),
    )
    context = runtime_server.AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("secret"),
        ctx=context,
    )

    assert result == {
        "error": "认证服务暂不可用"
    }
    assert context.response.status_code == 503
