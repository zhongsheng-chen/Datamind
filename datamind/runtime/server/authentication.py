"""运行时认证接口.

通过挂载的 Starlette 应用提供登录、令牌续期和退出接口，
使认证端点可以直接表达 HTTP 状态码、响应头和空响应体。

核心功能：
  - login: 使用本地用户名和密码登录
  - refresh: 续期并轮换刷新令牌
  - logout: 撤销刷新令牌
"""

from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    TokenError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.events import record_authentication_event
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from datamind.db.core import UnitOfWork
from datamind.audit.enums import AuditSource
from datamind.audit.recorder import AuditRecorder
from datamind.context import (
    generate_trace_id,
    is_valid_trace_id,
)
from datamind.context.keys import (
    HOSTNAME,
    IP,
    REQUEST_ID,
    SOURCE,
    TRACE_ID,
    USER,
)
from datamind.utils import (
    generate_random_id,
    get_hostname,
)


_RequestModel = TypeVar(
    "_RequestModel",
    bound=BaseModel,
)
logger = structlog.get_logger(__name__)


def _prepare_response(
        response: Response,
) -> Response:
    """为认证响应设置禁止缓存头."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return response


def _json_response(
        content: dict[str, object],
        *,
        status_code: int = 200,
) -> Response:
    """构造禁止缓存的 JSON 响应."""
    return _prepare_response(
        JSONResponse(
            content=content,
            status_code=status_code,
        )
    )


async def _parse_request(
        request: Request,
        model: type[_RequestModel],
) -> _RequestModel | Response:
    """解析并校验认证请求."""
    try:
        return model.model_validate_json(
            await request.body()
        )

    except ValidationError as exc:
        return _json_response(
            {
                "error": (
                    f"{exc.error_count()} validation error "
                    "for Input"
                ),
                "detail": exc.errors(
                    include_context=False,
                    include_input=False,
                ),
            },
            status_code=400,
        )


def _request_ip(
        request: Request,
) -> str | None:
    """读取客户端 IP."""
    client = request.client

    return (
        client.host
        if client is not None
        else None
    )


def _request_id(
        request: Request,
) -> str:
    """读取可信长度的请求 ID，缺失时生成新 ID."""
    request_id = request.headers.get(
        "x-request-id",
        "",
    ).strip()

    return (
        request_id
        if request_id and len(request_id) <= 64
        else generate_random_id(prefix="req")
    )


def _trace_id(
        request: Request,
) -> str:
    """读取 W3C 追踪 ID，缺失或无效时生成新 ID."""
    traceparent = request.headers.get(
        "traceparent",
        "",
    ).strip().lower()
    parts = traceparent.split("-")
    trace_id = (
        parts[1]
        if len(parts) == 4 and is_valid_trace_id(parts[1])
        else request.headers.get(
            "x-trace-id",
            "",
        ).strip().lower()
    )

    return (
        trace_id
        if is_valid_trace_id(trace_id)
        else generate_trace_id()
    )


def _authentication_context(
        request: Request,
        *,
        username: str,
) -> dict[str, object]:
    """构建运行时认证事件上下文."""
    return {
        USER: username,
        SOURCE: AuditSource.HTTP,
        IP: _request_ip(request),
        REQUEST_ID: _request_id(request),
        TRACE_ID: _trace_id(request),
        HOSTNAME: get_hostname(),
    }


async def _record_event(
        request: Request,
        *,
        action: str,
        actor_username: str,
        target_id: str,
        successful: bool,
        status_code: int,
        attempted_username: str | None = None,
        error: str | None = None,
        details: dict[str, object] | None = None,
) -> None:
    """记录运行时认证日志和审计事件."""
    await record_authentication_event(
        logger=logger,
        recorder=AuditRecorder(),
        channel="运行时",
        action=action,
        actor_username=actor_username,
        target_id=target_id,
        successful=successful,
        status_code=status_code,
        context=_authentication_context(
            request,
            username=actor_username,
        ),
        attempted_username=attempted_username,
        error=error,
        details=details,
    )


async def login(
        request: Request,
) -> Response:
    """使用本地用户名和密码登录."""
    login_request = await _parse_request(
        request,
        LoginRequest,
    )

    if isinstance(login_request, Response):
        await _record_event(
            request,
            action="auth.login",
            actor_username="anonymous",
            target_id="unknown",
            successful=False,
            status_code=login_request.status_code,
            error="登录请求无效",
        )
        return login_request

    try:
        authentication_failed = False
        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )

            try:
                tokens = await service.login(
                    login_request,
                    ip=_request_ip(request),
                    user_agent=request.headers.get(
                        "user-agent"
                    ),
                )
            except (
                    InvalidCredentialsError,
                    UserDisabledError,
                    UserLockedError,
            ):
                authentication_failed = True
    except (
            AuthError,
            SQLAlchemyError,
            ValueError,
    ):
        response = _json_response(
            {"error": "认证服务暂不可用"},
            status_code=503,
        )
        await _record_event(
            request,
            action="auth.login",
            actor_username="anonymous",
            attempted_username=login_request.username,
            target_id="unknown",
            successful=False,
            status_code=response.status_code,
            error="认证服务暂不可用",
        )
        return response

    if authentication_failed:
        response = _json_response(
            {"error": "用户名或密码错误"},
            status_code=401,
        )
        await _record_event(
            request,
            action="auth.login",
            actor_username="anonymous",
            attempted_username=login_request.username,
            target_id="unknown",
            successful=False,
            status_code=response.status_code,
            error="登录失败",
        )
        return response

    response = _json_response(
        tokens.model_dump(
            mode="json"
        )
    )
    await _record_event(
        request,
        action="auth.login",
        actor_username=login_request.username,
        target_id=login_request.username,
        successful=True,
        status_code=response.status_code,
    )
    return response


async def refresh(
        request: Request,
) -> Response:
    """续期并轮换刷新令牌."""
    refresh_request = await _parse_request(
        request,
        RefreshTokenRequest,
    )

    if isinstance(refresh_request, Response):
        return refresh_request

    try:
        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )

            try:
                tokens = await service.refresh(
                    refresh_request,
                    ip=_request_ip(request),
                    user_agent=request.headers.get(
                        "user-agent"
                    ),
                )
            except (
                    TokenError,
                    UserDisabledError,
                    UserLockedError,
            ):
                return _json_response(
                    {"error": "刷新令牌无效或已失效"},
                    status_code=401,
                )
    except (
            AuthError,
            SQLAlchemyError,
            ValueError,
    ):
        return _json_response(
            {"error": "认证服务暂不可用"},
            status_code=503,
        )

    return _json_response(
        tokens.model_dump(
            mode="json"
        )
    )


async def logout(
        request: Request,
) -> Response:
    """撤销刷新令牌."""
    logout_request = await _parse_request(
        request,
        LogoutRequest,
    )

    if isinstance(logout_request, Response):
        await _record_event(
            request,
            action="auth.logout",
            actor_username="anonymous",
            target_id="unknown",
            successful=False,
            status_code=logout_request.status_code,
            error="退出登录请求无效",
        )
        return logout_request

    try:
        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            logout_result = await service.logout(
                logout_request
            )
    except (
            AuthError,
            SQLAlchemyError,
            ValueError,
    ):
        response = _json_response(
            {"error": "认证服务暂不可用"},
            status_code=503,
        )
        await _record_event(
            request,
            action="auth.logout",
            actor_username="anonymous",
            target_id="unknown",
            successful=False,
            status_code=response.status_code,
            error="认证服务暂不可用",
        )
        return response

    response = _prepare_response(
        Response(
            status_code=204
        )
    )
    await _record_event(
        request,
        action="auth.logout",
        actor_username=(
            logout_result.username
            or logout_result.user_id
            or "anonymous"
        ),
        target_id=(
            logout_result.user_id
            or "unknown"
        ),
        successful=True,
        status_code=response.status_code,
        details={
            "revoked": logout_result.revoked,
        },
    )
    return response


auth_app = Starlette(
    routes=[
        Route(
            "/login",
            login,
            methods=["POST"],
        ),
        Route(
            "/refresh",
            refresh,
            methods=["POST"],
        ),
        Route(
            "/logout",
            logout,
            methods=["POST"],
        ),
    ]
)
