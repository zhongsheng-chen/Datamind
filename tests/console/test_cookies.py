"""管理控制台会话 Cookie 测试

验证访问令牌、刷新令牌和 CSRF Cookie 的写入、补发与清理行为。

核心功能：
  - test_set_session_cookies_writes_complete_session:
    验证完整会话写入
  - test_set_session_cookies_clears_missing_refresh_token:
    验证应急会话处理
  - test_ensure_csrf_cookie_only_writes_when_missing:
    验证 CSRF Cookie 补发
  - test_clear_session_cookies_expires_all_session_cookies:
    验证会话清理
"""

import importlib
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from datamind.auth.schemas import TokenResponse
from datamind.console.cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_session_cookies,
    ensure_csrf_cookie,
    set_session_cookies,
)


cookies_module = importlib.import_module(
    "datamind.console.cookies"
)


def create_request(
        *,
        scheme: str = "http",
        cookie: str | None = None,
) -> Request:
    """创建 Cookie 测试请求"""
    headers = []

    if cookie is not None:
        headers.append(
            (
                b"cookie",
                cookie.encode("ascii"),
            )
        )

    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": scheme,
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 50000),
        }
    )


@pytest.fixture(autouse=True)
def install_cookie_settings(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安装固定的 Cookie 配置和随机令牌"""
    monkeypatch.setitem(
        vars(cookies_module),
        "get_auth_config",
        lambda: SimpleNamespace(
            refresh_token_expires_days=7
        ),
    )
    monkeypatch.setitem(
        vars(cookies_module.secrets),
        "token_urlsafe",
        lambda _length: "csrf-token",
    )


def test_set_session_cookies_writes_complete_session() -> None:
    """测试 HTTPS 会话写入完整且安全的 Cookie"""
    response = Response()
    tokens = TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
    )

    set_session_cookies(
        response=response,
        request=create_request(scheme="https"),
        tokens=tokens,
    )

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 3
    assert any(
        cookie.startswith(
            f"{ACCESS_COOKIE}=access-token;"
        )
        and "HttpOnly" in cookie
        and "Max-Age=1800" in cookie
        and "SameSite=strict" in cookie
        and "Secure" in cookie
        for cookie in cookies
    )
    assert any(
        cookie.startswith(
            f"{REFRESH_COOKIE}=refresh-token;"
        )
        and "HttpOnly" in cookie
        and "Max-Age=604800" in cookie
        for cookie in cookies
    )
    assert any(
        cookie.startswith(
            f"{CSRF_COOKIE}=csrf-token;"
        )
        and "HttpOnly" not in cookie
        and "Max-Age=604800" in cookie
        for cookie in cookies
    )


def test_set_session_cookies_clears_missing_refresh_token() -> None:
    """测试不签发刷新令牌时清除旧刷新 Cookie"""
    response = Response()

    set_session_cookies(
        response=response,
        request=create_request(),
        tokens=TokenResponse(
            access_token="access-token",
            expires_in=300,
        ),
    )

    cookies = response.headers.getlist("set-cookie")
    refresh_cookie = next(
        cookie
        for cookie in cookies
        if cookie.startswith(
            f"{REFRESH_COOKIE}="
        )
    )
    assert "Max-Age=0" in refresh_cookie
    assert "Secure" not in refresh_cookie


def test_ensure_csrf_cookie_only_writes_when_missing() -> None:
    """测试仅在请求缺少 CSRF Cookie 时补发"""
    missing_response = Response()
    ensure_csrf_cookie(
        response=missing_response,
        request=create_request(),
    )

    assert missing_response.headers.getlist(
        "set-cookie"
    )[0].startswith(
        f"{CSRF_COOKIE}=csrf-token;"
    )

    existing_response = Response()
    ensure_csrf_cookie(
        response=existing_response,
        request=create_request(
            cookie=f"{CSRF_COOKIE}=existing"
        ),
    )

    assert existing_response.headers.getlist(
        "set-cookie"
    ) == []


def test_clear_session_cookies_expires_all_session_cookies() -> None:
    """测试清理全部控制台会话 Cookie"""
    response = Response()

    clear_session_cookies(response)

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 3

    for name in (
            ACCESS_COOKIE,
            REFRESH_COOKIE,
            CSRF_COOKIE,
    ):
        cookie = next(
            item
            for item in cookies
            if item.startswith(f"{name}=")
        )
        assert "Max-Age=0" in cookie
        assert "Path=/" in cookie
