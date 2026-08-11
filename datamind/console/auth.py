# datamind/console/auth.py

"""管理控制台浏览器认证

负责创建、轮换、撤销和验证浏览器登录会话。

核心功能：
  - login: 创建浏览器会话
  - refresh: 轮换浏览器会话
  - logout: 撤销浏览器会话
  - authenticate: 验证访问令牌
"""

from collections.abc import Callable
from typing import Any

from pydantic import (
    SecretStr,
    ValidationError,
)
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    Response,
)

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
)


async def login(
        request: Request,
        *,
        unit_of_work: Callable[[], Any],
        auth_service: Callable[..., Any],
        user_payload: Callable[[AuthenticatedUser], dict[str, object]],
        client_ip: Callable[[Request], str | None],
        error_response: Callable[..., JSONResponse],
        set_session_cookies: Callable[..., None],
) -> JSONResponse:
    """使用本地账户创建浏览器会话"""
    try:
        payload = await request.json()
        login_request = LoginRequest.model_validate(
            payload
        )
        tokens: TokenResponse | None = None
        user: AuthenticatedUser | None = None

        async with unit_of_work() as uow:
            service = auth_service(
                session=uow.session
            )
            login_error: (
                InvalidCredentialsError
                | UserDisabledError
                | UserLockedError
                | None
            ) = None

            try:
                issued_tokens = await service.login(
                    login_request,
                    ip=client_ip(request),
                    user_agent=request.headers.get(
                        "user-agent"
                    ),
                )
            except (
                    InvalidCredentialsError,
                    UserDisabledError,
                    UserLockedError,
            ) as authentication_error:
                login_error = authentication_error
            else:
                tokens = issued_tokens
                user = await service.authenticate_access_token(
                    issued_tokens.access_token
                )

        if login_error is not None:
            raise login_error

        if tokens is None or user is None:
            raise AuthError(
                "登录服务未返回有效会话"
            )

        request.state.authenticated_user = user

    except UserDisabledError:
        return error_response(
            "用户已停用，请联系管理员",
            status_code=403,
        )
    except UserLockedError:
        return error_response(
            "用户已锁定，请稍后重试或联系管理员",
            status_code=403,
        )
    except (
            AuthError,
            ValidationError,
            ValueError,
    ):
        return error_response(
            "用户名或密码错误",
            status_code=401,
        )
    except SQLAlchemyError:
        return error_response(
            "认证服务暂不可用",
            status_code=503,
        )

    response = JSONResponse(
        user_payload(user)
    )
    set_session_cookies(
        response=response,
        request=request,
        tokens=tokens,
    )

    return response


async def refresh(
        request: Request,
        *,
        refresh_cookie: str,
        unit_of_work: Callable[[], Any],
        auth_service: Callable[..., Any],
        client_ip: Callable[[Request], str | None],
        error_response: Callable[..., JSONResponse],
        set_session_cookies: Callable[..., None],
        clear_session_cookies: Callable[[Response], None],
) -> Response:
    """轮换浏览器登录凭据"""
    refresh_token = request.cookies.get(
        refresh_cookie
    )

    if refresh_token is None:
        return error_response(
            "登录会话已过期",
            status_code=401,
        )

    try:
        async with unit_of_work() as uow:
            service = auth_service(
                session=uow.session
            )
            tokens = await service.refresh(
                RefreshTokenRequest(
                    refresh_token=SecretStr(
                        refresh_token
                    )
                ),
                ip=client_ip(request),
                user_agent=request.headers.get(
                    "user-agent"
                ),
            )
    except AuthError:
        response = error_response(
            "登录会话已失效",
            status_code=401,
        )
        clear_session_cookies(
            response
        )
        return response
    except SQLAlchemyError:
        return error_response(
            "认证服务暂不可用",
            status_code=503,
        )

    response = Response(
        status_code=204
    )
    set_session_cookies(
        response=response,
        request=request,
        tokens=tokens,
    )

    return response


async def logout(
        request: Request,
        *,
        refresh_cookie: str,
        unit_of_work: Callable[[], Any],
        auth_service: Callable[..., Any],
        clear_session_cookies: Callable[[Response], None],
) -> Response:
    """撤销浏览器会话"""
    refresh_token = request.cookies.get(
        refresh_cookie
    )
    request.state.logout_revocation_failed = False

    if refresh_token is not None:
        try:
            async with unit_of_work() as uow:
                service = auth_service(
                    session=uow.session
                )
                request.state.logout_token_revoked = await service.logout(
                    LogoutRequest(
                        refresh_token=SecretStr(
                            refresh_token
                        )
                    )
                )
        except (
                AuthError,
                SQLAlchemyError,
        ):
            request.state.logout_revocation_failed = True

    response = Response(
        status_code=204
    )
    clear_session_cookies(
        response
    )

    return response


async def authenticate(
        request: Request,
        *,
        access_cookie: str,
        unit_of_work: Callable[[], Any],
        auth_service: Callable[..., Any],
) -> AuthenticatedUser | None:
    """认证浏览器访问令牌"""
    access_token = request.cookies.get(
        access_cookie
    )

    if access_token is None:
        return None

    try:
        async with unit_of_work() as uow:
            service = auth_service(
                session=uow.session
            )
            return await service.authenticate_access_token(
                access_token
            )
    except (
            AuthError,
            SQLAlchemyError,
    ):
        return None
