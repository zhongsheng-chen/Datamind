# tests/console/test_auth.py

"""管理控制台认证会话测试

验证浏览器登录、令牌轮换、会话查询和退出登录行为。

核心功能：
  - test_login_rejects_invalid_credentials: 验证登录失败响应
  - test_refresh_rotates_session_cookies: 验证会话令牌轮换
  - test_refresh_clears_invalid_session: 验证失效会话清理
  - test_logout_revokes_refresh_token: 验证退出登录
  - test_session_returns_authenticated_user: 验证会话用户查询
"""

import importlib
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)
from sqlalchemy.exc import SQLAlchemyError

from datamind.auth.enums import UserStatus
from datamind.auth.errors import AuthError
from datamind.auth.schemas import (
    AuthenticatedUser,
    TokenResponse,
)


app_module = importlib.import_module(
    "datamind.console.app"
)


class FakeUnitOfWork:
    """控制台认证测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user() -> AuthenticatedUser:
    """创建已认证控制台用户"""
    return AuthenticatedUser(
        user_id="usr_alice",
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        status=UserStatus.ACTIVE,
        roles=[
            "developer"
        ],
        permissions=[
            "model.read"
        ],
    )


def install_auth_service(
        monkeypatch: pytest.MonkeyPatch,
        service: MagicMock,
) -> None:
    """安装认证服务和隔离配置替身"""
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "create_auth_service",
        lambda *, session: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_settings",
        lambda: SimpleNamespace(
            auth=SimpleNamespace(
                refresh_token_expires_days=7
            )
        ),
    )


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录拒绝无效用户名或密码"""
    service = MagicMock()
    service.login = AsyncMock(
        side_effect=AuthError(
            "invalid credentials"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/login",
            json={
                "username": "alice",
                "password": "wrong",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "用户名或密码错误"
    }


@pytest.mark.asyncio
async def test_login_reports_unavailable_database(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录在数据库异常时返回服务不可用"""
    service = MagicMock()
    service.login = AsyncMock(
        side_effect=SQLAlchemyError(
            "database unavailable"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/login",
            json={
                "username": "alice",
                "password": "secret",
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": "认证服务暂不可用"
    }


@pytest.mark.asyncio
async def test_login_without_refresh_token_clears_refresh_cookie(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试无刷新令牌的登录会话清理旧 Cookie"""
    service = MagicMock()
    service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token=None,
            expires_in=1800,
        )
    )
    service.authenticate_access_token = AsyncMock(
        return_value=create_user()
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="https://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "old-token",
        )
        response = await client.post(
            "/api/login",
            json={
                "username": "alice",
                "password": "secret",
            },
        )

    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert response.status_code == 200
    assert any(
        "datamind_console_access=access-token" in cookie
        and "Secure" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_refresh=" in cookie
        and "Max-Age=0" in cookie
        for cookie in cookies
    )


@pytest.mark.asyncio
async def test_refresh_requires_refresh_cookie() -> None:
    """测试会话轮换要求刷新令牌 Cookie"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/refresh"
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "登录会话已过期"
    }


@pytest.mark.asyncio
async def test_refresh_rotates_session_cookies(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试会话续期轮换访问令牌和刷新令牌"""
    service = MagicMock()
    service.refresh = AsyncMock(
        return_value=TokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=1800,
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "old-refresh-token",
        )
        response = await client.post(
            "/api/refresh"
        )

    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert response.status_code == 204
    assert any(
        "datamind_console_access=new-access-token" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_refresh=new-refresh-token" in cookie
        for cookie in cookies
    )
    refresh_call = service.refresh.await_args
    assert refresh_call is not None
    refresh_request = refresh_call.args[0]
    assert (
        refresh_request.refresh_token.get_secret_value()
        == "old-refresh-token"
    )


@pytest.mark.asyncio
async def test_refresh_clears_invalid_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新令牌失效时清理浏览器会话"""
    service = MagicMock()
    service.refresh = AsyncMock(
        side_effect=AuthError(
            "invalid refresh token"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "invalid-token",
        )
        response = await client.post(
            "/api/refresh"
        )

    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert response.status_code == 401
    assert response.json() == {
        "error": "登录会话已失效"
    }
    assert sum(
        "Max-Age=0" in cookie
        for cookie in cookies
    ) == 2


@pytest.mark.asyncio
async def test_refresh_reports_unavailable_database(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试会话续期在数据库异常时返回服务不可用"""
    service = MagicMock()
    service.refresh = AsyncMock(
        side_effect=SQLAlchemyError(
            "database unavailable"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "refresh-token",
        )
        response = await client.post(
            "/api/refresh"
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": "认证服务暂不可用"
    }


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退出登录撤销刷新令牌并清理 Cookie"""
    service = MagicMock()
    service.logout = AsyncMock()
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "refresh-token",
        )
        response = await client.post(
            "/api/logout"
        )

    assert response.status_code == 204
    logout_call = service.logout.await_args
    assert logout_call is not None
    logout_request = logout_call.args[0]
    assert (
        logout_request.refresh_token.get_secret_value()
        == "refresh-token"
    )
    assert sum(
        "Max-Age=0" in cookie
        for cookie in response.headers.get_list(
            "set-cookie"
        )
    ) == 2


@pytest.mark.asyncio
async def test_logout_ignores_revocation_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试令牌撤销失败时仍完成本地退出"""
    service = MagicMock()
    service.logout = AsyncMock(
        side_effect=SQLAlchemyError(
            "database unavailable"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_refresh",
            "refresh-token",
        )
        response = await client.post(
            "/api/logout"
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_session_returns_authenticated_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试会话接口返回访问令牌对应的用户"""
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=create_user()
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_access",
            "access-token",
        )
        response = await client.get(
            "/api/session"
        )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    service.authenticate_access_token.assert_awaited_once_with(
        "access-token"
    )


@pytest.mark.asyncio
async def test_session_rejects_invalid_access_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试会话接口拒绝无效访问令牌"""
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        side_effect=AuthError(
            "invalid access token"
        )
    )
    install_auth_service(
        monkeypatch,
        service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_access",
            "invalid-token",
        )
        response = await client.get(
            "/api/session"
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "尚未登录"
    }
