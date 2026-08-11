# datamind/console/cookies.py

"""管理控制台浏览器会话 Cookie

负责写入、补发和清除访问令牌、刷新令牌与 CSRF Cookie。

核心功能：
  - set_session_cookies: 写入浏览器会话 Cookie
  - ensure_csrf_cookie: 补发缺失的 CSRF Cookie
  - clear_session_cookies: 清除浏览器会话 Cookie
"""

import secrets

from starlette.requests import Request
from starlette.responses import Response

from datamind.auth.schemas import TokenResponse
from datamind.config import get_settings


ACCESS_COOKIE = "datamind_console_access"
REFRESH_COOKIE = "datamind_console_refresh"
CSRF_COOKIE = "datamind_console_csrf"


def set_session_cookies(
        *,
        response: Response,
        request: Request,
        tokens: TokenResponse,
) -> None:
    """写入浏览器会话 Cookie"""
    secure = request.url.scheme == "https"
    refresh_seconds = _refresh_cookie_seconds()
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=tokens.expires_in,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=refresh_seconds,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )

    if tokens.refresh_token is None:
        response.delete_cookie(
            REFRESH_COOKIE,
            path="/",
        )
        return

    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=refresh_seconds,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def ensure_csrf_cookie(
        *,
        response: Response,
        request: Request,
) -> None:
    """为有效浏览器会话补发缺失的 CSRF Cookie"""
    if request.cookies.get(
            CSRF_COOKIE
    ) is not None:
        return

    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=_refresh_cookie_seconds(),
        httponly=False,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )


def clear_session_cookies(
        response: Response,
) -> None:
    """清除浏览器会话 Cookie"""
    for name in (
            ACCESS_COOKIE,
            REFRESH_COOKIE,
            CSRF_COOKIE,
    ):
        response.delete_cookie(
            name,
            path="/",
        )


def _refresh_cookie_seconds() -> int:
    """返回刷新会话 Cookie 的有效秒数"""
    return (
        get_settings().auth.refresh_token_expires_days
        * 24
        * 60
        * 60
    )
