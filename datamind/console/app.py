# datamind/console/app.py

"""管理控制台 ASGI 应用

提供浏览器登录、会话续期、实时变更通知和按权限裁剪的只读控制台数据。

核心功能：
  - console_app: Starlette 管理控制台应用

使用示例：
  from datamind.console.app import console_app
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import (
    SecretStr,
    ValidationError,
)
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import (
    Mount,
    Route,
)
from starlette.staticfiles import StaticFiles
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from datamind.auth.errors import AuthError
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.models.outbox import OutboxEvent
from datamind.db.repositories import OutboxRepository
from datamind.console.events import event_broker
from datamind.services import DashboardService


_STATIC_DIR = Path(
    __file__
).parent / "static"
_ACCESS_COOKIE = "datamind_console_access"
_REFRESH_COOKIE = "datamind_console_refresh"
_EVENT_BATCH_SIZE = 200
_EVENT_HEARTBEAT_SECONDS = 15
_EVENT_AUTH_CHECK_SECONDS = 60


class SecurityHeadersMiddleware:
    """为控制台响应增加浏览器安全头"""

    def __init__(
            self,
            app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
    ) -> None:
        async def send_with_headers(
                message: Message,
        ) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(
                    scope=message
                )
                headers["content-security-policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self'; "
                    "img-src 'self' data:; "
                    "connect-src 'self'; "
                    "object-src 'none'; "
                    "base-uri 'self'; "
                    "frame-ancestors 'none'; "
                    "form-action 'self'"
                )
                headers["x-content-type-options"] = "nosniff"
                headers["referrer-policy"] = "no-referrer"
                headers["permissions-policy"] = (
                    "camera=(), microphone=(), geolocation=()"
                )

                if scope.get("scheme") == "https":
                    headers["strict-transport-security"] = (
                        "max-age=31536000"
                    )

            await send(
                message
            )

        await self.app(
            scope,
            receive,
            send_with_headers,
        )


def _security_headers_middleware(
        app: ASGIApp,
        /,
) -> ASGIApp:
    """创建安全响应头中间件"""
    return SecurityHeadersMiddleware(
        app
    )


async def _page(
        _request: Request,
) -> FileResponse:
    """返回管理控制台页面"""
    return FileResponse(
        _STATIC_DIR / "index.html"
    )


async def _login(
        request: Request,
) -> JSONResponse:
    """使用本地账户创建浏览器会话"""
    try:
        payload = await request.json()
        login_request = LoginRequest.model_validate(
            payload
        )

        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            tokens = await service.login(
                login_request,
                ip=_client_ip(request),
                user_agent=request.headers.get(
                    "user-agent"
                ),
            )
            user = await service.authenticate_access_token(
                tokens.access_token
            )

    except (
            AuthError,
            ValidationError,
            ValueError,
    ):
        return _error_response(
            "用户名或密码错误",
            status_code=401,
        )
    except SQLAlchemyError:
        return _error_response(
            "认证服务暂不可用",
            status_code=503,
        )

    response = JSONResponse(
        _user_payload(user)
    )
    _set_session_cookies(
        response=response,
        request=request,
        tokens=tokens,
    )

    return response


async def _refresh(
        request: Request,
) -> Response:
    """轮换浏览器登录凭据"""
    refresh_token = request.cookies.get(
        _REFRESH_COOKIE
    )

    if refresh_token is None:
        return _error_response(
            "登录会话已过期",
            status_code=401,
        )

    try:
        async with UnitOfWork() as uow:
            service = create_auth_service(
                session=uow.session
            )
            tokens = await service.refresh(
                RefreshTokenRequest(
                    refresh_token=SecretStr(
                        refresh_token
                    )
                ),
                ip=_client_ip(request),
                user_agent=request.headers.get(
                    "user-agent"
                ),
            )
    except AuthError:
        response = _error_response(
            "登录会话已失效",
            status_code=401,
        )
        _clear_session_cookies(
            response
        )
        return response
    except SQLAlchemyError:
        return _error_response(
            "认证服务暂不可用",
            status_code=503,
        )

    response = Response(
        status_code=204
    )
    _set_session_cookies(
        response=response,
        request=request,
        tokens=tokens,
    )

    return response


async def _logout(
        request: Request,
) -> Response:
    """撤销浏览器会话"""
    refresh_token = request.cookies.get(
        _REFRESH_COOKIE
    )

    if refresh_token is not None:
        try:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )
                await service.logout(
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
            pass

    response = Response(
        status_code=204
    )
    _clear_session_cookies(
        response
    )

    return response


async def _session(
        request: Request,
) -> JSONResponse:
    """返回当前浏览器登录用户"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    return JSONResponse(
        _user_payload(user)
    )


async def _overview(
        request: Request,
) -> JSONResponse:
    """返回按权限裁剪的控制台快照"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    try:
        snapshot = await DashboardService().snapshot(
            permissions=user.permissions,
        )
    except SQLAlchemyError:
        return _error_response(
            "控制台数据暂不可用",
            status_code=503,
        )

    return JSONResponse(
        snapshot
    )


async def _model_versions(
        request: Request,
) -> JSONResponse:
    """返回模型版本分页数据"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    service = DashboardService()

    if not service.get_access(
            user.permissions
    )["models"]:
        return _error_response(
            "没有模型查看权限",
            status_code=403,
        )

    try:
        page = int(
            request.query_params.get(
                "page",
                "1",
            )
        )
        page_size = int(
            request.query_params.get(
                "page_size",
                "10",
            )
        )
        query = request.query_params.get(
            "q",
            "",
        )
        sort_by = request.query_params.get(
            "sort"
        )
        sort_order = request.query_params.get(
            "order",
            "asc",
        )
        result = await service.get_model_versions(
            model_id=request.path_params[
                "model_id"
            ],
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as error:
        return _error_response(
            str(error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "模型版本数据暂不可用",
            status_code=503,
        )

    return JSONResponse(
        result
    )


async def _section(
        request: Request,
) -> JSONResponse:
    """返回控制台页面分页数据"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    section = request.path_params[
        "section"
    ]
    service = DashboardService()
    access = service.get_access(
        user.permissions
    )

    if section not in access:
        return _error_response(
            "控制台页面不存在",
            status_code=404,
        )

    if not access[section]:
        return _error_response(
            "没有页面查看权限",
            status_code=403,
        )

    try:
        page = int(
            request.query_params.get(
                "page",
                "1",
            )
        )
        page_size = int(
            request.query_params.get(
                "page_size",
                "10",
            )
        )
        query = request.query_params.get(
            "q",
            "",
        )
        sort_by = request.query_params.get(
            "sort"
        )
        sort_order = request.query_params.get(
            "order",
            "asc",
        )
        result = await service.get_section(
            section=section,
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as error:
        return _error_response(
            str(error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "控制台页面数据暂不可用",
            status_code=503,
        )

    return JSONResponse(
        result
    )


async def _experiment_variants(
        request: Request,
) -> JSONResponse:
    """返回实验分组分页数据"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    service = DashboardService()

    if not service.get_access(
            user.permissions
    )["experiments"]:
        return _error_response(
            "没有实验查看权限",
            status_code=403,
        )

    try:
        page = int(
            request.query_params.get(
                "page",
                "1",
            )
        )
        page_size = int(
            request.query_params.get(
                "page_size",
                "10",
            )
        )
        query = request.query_params.get(
            "q",
            "",
        )
        sort_by = request.query_params.get(
            "sort"
        )
        sort_order = request.query_params.get(
            "order",
            "asc",
        )
        result = await service.get_experiment_variants(
            experiment_id=request.path_params[
                "experiment_id"
            ],
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as error:
        return _error_response(
            str(error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "实验分组数据暂不可用",
            status_code=503,
        )

    return JSONResponse(
        result
    )


async def _events(
        request: Request,
) -> Response:
    """建立控制台实时事件流"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    access = DashboardService.get_access(
        user.permissions
    )
    allowed_topics = {
        topic
        for topic, granted in access.items()
        if granted
    }

    return StreamingResponse(
        _stream_events(
            request=request,
            allowed_topics=allowed_topics,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_events(
        *,
        request: Request,
        allowed_topics: set[str],
) -> AsyncIterator[str]:
    """推送当前用户有权接收的控制台事件"""
    cursor = _parse_event_cursor(
        request.headers.get(
            "last-event-id"
        )
    )
    loop = asyncio.get_running_loop()
    last_auth_check = loop.time()

    async with event_broker.subscribe() as notifications:
        oldest_event_id, latest_event_id = await _get_event_window()

        if (
                cursor is None
                or cursor > latest_event_id
                or (
                    oldest_event_id is not None
                    and cursor < oldest_event_id - 1
                )
        ):
            cursor = latest_event_id
            yield _encode_sse(
                event="sync",
                event_id=cursor,
                data={
                    "topics": sorted(
                        allowed_topics
                    )
                },
                retry=3000,
            )

        while True:
            events = await _get_events_after(
                cursor
            )

            if events:
                cursor = int(
                    events[-1].event_id
                )
                topics = sorted({
                    event.topic
                    for event in events
                    if event.topic in allowed_topics
                })

                yield _encode_sse(
                    event=(
                        "changed"
                        if topics
                        else "cursor"
                    ),
                    event_id=cursor,
                    data={
                        "topics": topics
                    },
                )

                if len(events) == _EVENT_BATCH_SIZE:
                    continue

            if await request.is_disconnected():
                return

            try:
                await asyncio.wait_for(
                    notifications.get(),
                    timeout=_EVENT_HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                now = loop.time()

                if (
                        now - last_auth_check
                        >= _EVENT_AUTH_CHECK_SECONDS
                ):
                    if await _authenticate(request) is None:
                        yield _encode_sse(
                            event="authentication",
                            data={
                                "status": "expired"
                            },
                        )
                        return

                    last_auth_check = now

                yield ": keep-alive\n\n"


async def _get_event_window() -> tuple[int | None, int]:
    """获取当前可回放事件游标范围"""
    async with UnitOfWork() as uow:
        repository = OutboxRepository(
            uow.session
        )
        oldest_event_id = await repository.get_oldest_event_id()
        latest_event_id = await repository.get_latest_event_id()

    return oldest_event_id, latest_event_id or 0


async def _get_events_after(
        event_id: int,
) -> list[OutboxEvent]:
    """读取指定游标之后的一批事件"""
    async with UnitOfWork() as uow:
        return await OutboxRepository(
            uow.session
        ).list_events(
            after_event_id=event_id,
            limit=_EVENT_BATCH_SIZE,
        )


def _parse_event_cursor(
        value: str | None,
) -> int | None:
    """解析 SSE 断线恢复游标"""
    if value is None:
        return None

    try:
        event_id = int(
            value
        )
    except ValueError:
        return None

    return (
        event_id
        if event_id >= 0
        else None
    )


def _encode_sse(
        *,
        event: str,
        data: dict[str, object],
        event_id: int | None = None,
        retry: int | None = None,
) -> str:
    """编码单条 SSE 消息"""
    fields: list[str] = []

    if retry is not None:
        fields.append(
            f"retry: {retry}"
        )

    if event_id is not None:
        fields.append(
            f"id: {event_id}"
        )

    fields.extend((
        f"event: {event}",
        "data: " + json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "",
        "",
    ))

    return "\n".join(
        fields
    )


async def _authenticate(
        request: Request,
) -> AuthenticatedUser | None:
    """认证浏览器访问令牌"""
    access_token = request.cookies.get(
        _ACCESS_COOKIE
    )

    if access_token is None:
        return None

    try:
        async with UnitOfWork() as uow:
            service = create_auth_service(
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


def _set_session_cookies(
        *,
        response: Response,
        request: Request,
        tokens: TokenResponse,
) -> None:
    """写入安全浏览器会话 Cookie"""
    secure = request.url.scheme == "https"
    response.set_cookie(
        _ACCESS_COOKIE,
        tokens.access_token,
        max_age=tokens.expires_in,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )

    if tokens.refresh_token is None:
        response.delete_cookie(
            _REFRESH_COOKIE,
            path="/",
        )
        return

    refresh_seconds = (
        get_settings().auth.refresh_token_expires_days
        * 24
        * 60
        * 60
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=refresh_seconds,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def _clear_session_cookies(
        response: Response,
) -> None:
    """删除浏览器会话 Cookie"""
    response.delete_cookie(
        _ACCESS_COOKIE,
        path="/",
    )
    response.delete_cookie(
        _REFRESH_COOKIE,
        path="/",
    )


def _user_payload(
        user: AuthenticatedUser,
) -> dict[str, object]:
    """转换当前用户信息"""
    return user.model_dump(
        mode="json"
    )


def _client_ip(
        request: Request,
) -> str | None:
    """读取客户端 IP"""
    client = request.client

    if client is None:
        return None

    return client.host


def _error_response(
        message: str,
        *,
        status_code: int,
) -> JSONResponse:
    """创建统一错误响应"""
    return JSONResponse(
        {
            "error": message
        },
        status_code=status_code,
    )


async def _health(
        _request: Request,
) -> JSONResponse:
    """返回管理控制台健康状态"""
    return JSONResponse({
        "status": "ok",
    })


@asynccontextmanager
async def _lifespan(
        _app: Starlette,
) -> AsyncIterator[None]:
    """管理控制台实时事件监听生命周期"""
    await event_broker.start()

    try:
        yield
    finally:
        await event_broker.stop()


console_app = Starlette(
    debug=False,
    lifespan=_lifespan,
    middleware=[
        Middleware(
            _security_headers_middleware
        )
    ],
    routes=[
        Route(
            "/health",
            _health,
            methods=["GET"],
        ),
        Route(
            "/",
            _page,
            methods=["GET"],
        ),
        Route(
            "/api/login",
            _login,
            methods=["POST"],
        ),
        Route(
            "/api/refresh",
            _refresh,
            methods=["POST"],
        ),
        Route(
            "/api/logout",
            _logout,
            methods=["POST"],
        ),
        Route(
            "/api/session",
            _session,
            methods=["GET"],
        ),
        Route(
            "/api/overview",
            _overview,
            methods=["GET"],
        ),
        Route(
            "/api/models/{model_id:str}/versions",
            _model_versions,
            methods=["GET"],
        ),
        Route(
            "/api/experiments/{experiment_id:str}/variants",
            _experiment_variants,
            methods=["GET"],
        ),
        Route(
            "/api/sections/{section:str}",
            _section,
            methods=["GET"],
        ),
        Route(
            "/api/events",
            _events,
            methods=["GET"],
        ),
        Mount(
            "/assets",
            app=StaticFiles(
                directory=(
                    _STATIC_DIR
                    / "assets"
                )
            ),
            name="assets",
        ),
    ],
)
