"""运行时认证接口测试.

验证认证 ASGI 应用的挂载、请求校验、令牌响应和错误处理。

核心功能：
  - test_auth_app_is_mounted_under_auth_path:
    验证认证 ASGI 应用挂载到 /auth
  - test_login_returns_tokens_without_cache:
    验证登录签发令牌并禁止缓存响应
  - test_login_hides_authentication_failure:
    验证登录失败不暴露账户状态
  - test_refresh_rotates_tokens:
    验证刷新接口续期并轮换令牌
  - test_refresh_hides_invalid_token_details:
    验证刷新失败返回统一认证错误
  - test_logout_is_idempotent_and_has_no_body:
    验证退出登录幂等并返回空响应体
  - test_auth_request_validation_returns_http_400:
    验证认证请求校验失败时返回 HTTP 400
  - test_login_reports_unavailable_auth_service:
    验证认证服务不可用时返回 HTTP 503
"""

from importlib import import_module
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from datamind.auth.schemas import (
    LogoutResult,
    TokenResponse,
)


def _authentication_module() -> Any:
    """返回运行时认证模块."""
    return import_module(
        "datamind.runtime.server.authentication"
    )


def _install_auth_service(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        auth_service: MagicMock,
) -> tuple[MagicMock, MagicMock]:
    """为认证 ASGI 应用安装服务替身."""
    authentication = _authentication_module()
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    auth_logger = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "UnitOfWork",
        runtime_server.FakeUnitOfWork,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "create_auth_service",
        lambda **_kwargs: auth_service,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "AuditRecorder",
        lambda: audit_recorder,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "logger",
        auth_logger,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "get_hostname",
        lambda: "runtime-host",
    )
    return audit_recorder, auth_logger


def test_auth_app_is_mounted_under_auth_path(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证 ASGI 应用挂载到 /auth."""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    authentication = _authentication_module()
    mounted_apps = (
        service_module
        .DatamindRuntimeService
        .mount_apps
    )

    assert mounted_apps == [
        (
            authentication.auth_app,
            "/auth",
            None,
        )
    ]
    assert {
        route.path
        for route in authentication.auth_app.routes
    } == {
        "/login",
        "/refresh",
        "/logout",
    }
    assert not {
        "login",
        "refresh",
        "logout",
    } & set(
        service_module.DatamindRuntimeService.apis
    )


@pytest.mark.asyncio
async def test_login_returns_tokens_without_cache(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地登录签发不缓存的令牌响应."""
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=1800,
        )
    )
    audit_recorder, auth_logger = _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/login",
            json={
                "username": "alice",
                "password": "secret",
            },
            headers={
                "user-agent": "pytest",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "expires_in": 1800,
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
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
    audit_recorder.record.assert_awaited_once()
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["action"] == "auth.login"
    assert audit_call.kwargs["target_id"] == "alice"
    assert audit_call.kwargs["status"] == "success"
    assert audit_call.kwargs["context"]["hostname"] == (
        "runtime-host"
    )
    auth_logger.info.assert_called_once()
    recorded = f"{audit_call!r}{auth_logger.info.call_args!r}"
    assert "secret" not in recorded
    assert "access-token" not in recorded
    assert "refresh-token" not in recorded


@pytest.mark.asyncio
async def test_login_hides_authentication_failure(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录失败不暴露账户状态."""
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        side_effect=InvalidCredentialsError()
    )
    audit_recorder, auth_logger = _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/login",
            json={
                "username": "alice",
                "password": "invalid",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "用户名或密码错误"
    }
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["action"] == "auth.login"
    assert audit_call.kwargs["target_id"] == "unknown"
    assert audit_call.kwargs["status"] == "failed"
    assert audit_call.kwargs["context"][
        "attempted_username"
    ] == "alice"
    auth_logger.warning.assert_called_once()
    assert "invalid" not in (
        f"{audit_call!r}{auth_logger.warning.call_args!r}"
    )


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新接口轮换访问令牌和刷新令牌."""
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        return_value=TokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=1800,
        )
    )
    _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/refresh",
            json={
                "refresh_token": "refresh-token",
            },
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == (
        "new-access-token"
    )
    assert response.json()["refresh_token"] == (
        "new-refresh-token"
    )
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
    """测试刷新失败返回统一认证错误."""
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        side_effect=InvalidRefreshTokenError()
    )
    _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/refresh",
            json={
                "refresh_token": "invalid",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "刷新令牌无效或已失效"
    }


@pytest.mark.asyncio
async def test_logout_is_idempotent_and_has_no_body(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退出接口幂等撤销令牌并返回空响应."""
    auth_service = MagicMock()
    auth_service.logout = AsyncMock(
        return_value=LogoutResult(
            revoked=True,
            user_id="usr_alice",
            username="alice",
        )
    )
    audit_recorder, auth_logger = _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/logout",
            json={
                "refresh_token": "refresh-token",
            },
        )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    auth_service.logout.assert_awaited_once()
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["action"] == "auth.logout"
    assert audit_call.kwargs["target_id"] == "usr_alice"
    assert audit_call.kwargs["status"] == "success"
    assert audit_call.kwargs["context"]["user"] == "alice"
    assert audit_call.kwargs["after"] == {
        "status_code": 204,
        "revoked": True,
    }
    auth_logger.info.assert_called_once()
    assert "refresh-token" not in (
        f"{audit_call!r}{auth_logger.info.call_args!r}"
    )


@pytest.mark.asyncio
async def test_auth_request_validation_returns_http_400(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证请求校验错误映射为 HTTP 400."""
    auth_service = MagicMock()
    _install_auth_service(
        runtime_server,
        monkeypatch,
        auth_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=_authentication_module().auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/logout",
            content=b'{"refresh_token":',
            headers={
                "content-type": "application/json",
            },
        )

    assert response.status_code == 400
    result = response.json()
    assert result["error"] == (
        "1 validation error for Input"
    )
    assert result["detail"][0]["type"] == "json_invalid"
    auth_service.logout.assert_not_called()


@pytest.mark.asyncio
async def test_login_reports_unavailable_auth_service(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证配置不可用时返回 HTTP 503."""
    authentication = _authentication_module()
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    auth_logger = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "UnitOfWork",
        runtime_server.FakeUnitOfWork,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "create_auth_service",
        MagicMock(
            side_effect=AuthError()
        ),
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "AuditRecorder",
        lambda: audit_recorder,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        authentication,
        "logger",
        auth_logger,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=authentication.auth_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/login",
            json={
                "username": "alice",
                "password": "secret",
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": "认证服务暂不可用"
    }
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["action"] == "auth.login"
    assert audit_call.kwargs["status"] == "failed"
    auth_logger.error.assert_called_once()
    auth_logger.warning.assert_not_called()
