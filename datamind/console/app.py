"""管理控制台 ASGI 应用

提供浏览器登录、会话续期、实时变更通知、数据查询和资源管理功能。

核心功能：
  - console_app: Starlette 管理控制台应用

使用示例：
  from datamind.console.app import console_app
"""

import asyncio
import json
import secrets
import tempfile
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
)
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    TypeVar,
)

import structlog
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.types import ASGIApp

from datamind.auth.enums import RoleStatus
from datamind.auth.events import record_authentication_event
from datamind.auth.factory import create_auth_service
from datamind.auth.permissions import has_permission
from datamind.auth.schemas import (
    AuthenticatedUser,
    LogoutResult,
)
from datamind.audit.enums import AuditSource
from datamind.audit.recorder import AuditRecorder
from datamind.context.keys import (
    HOSTNAME,
    IP,
    REQUEST_ID,
    SOURCE,
    TRACE_ID,
    USER,
)
from datamind.context import (
    generate_trace_id,
    is_valid_trace_id,
)
from datamind.context.core import update_context
from datamind.constants import (
    MB,
    SUPPORTED_MODEL_TYPES,
    SUPPORTED_PERMISSIONS,
)
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.models.outbox import OutboxEvent
from datamind.db.repositories import (
    MetadataRepository,
    OutboxRepository,
    VersionRepository,
)
from datamind.console.events import event_broker
from datamind.console.assets import ConsoleStaticFiles
from datamind.console import auth as browser_auth
from datamind.console import cookies as browser_cookies
from datamind.console.exports import (
    encode_csv_row as _encode_csv_row,
    export_filename as _export_filename,
)
from datamind.console.middleware import (
    RequestContextMiddleware,
    security_headers,
)
from datamind.console.routes import (
    ConsoleHandlers,
    create_routes,
)
from datamind.console.responses import (
    client_ip as _client_ip,
    error_response as _error_response,
)
from datamind.console.actions import (
    dispatch_resource_action,
)
from datamind.runtime.routing.schema import (
    ROUTING_RULES_EXAMPLE,
    RoutingRules,
)
from datamind.console.schemas import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
    ExperimentCreateRequest,
    ExperimentUpdateRequest,
    ModelRegistrationMetadata,
    ModelUpdateRequest,
    VersionUpdateRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    ResourceActionRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    RoutingCreateRequest,
    RoutingUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
    VariantCreateRequest,
    VariantUpdateRequest,
)
from datamind.models.errors import (
    ExperimentError,
    ModelError,
)
from datamind.services import (
    DashboardService,
    DeploymentLifecycleService,
    ExperimentLifecycleService,
    IdentityService,
    ModelCatalogService,
    ModelDeletionService,
    ModelLifecycleService,
    ModelRegistrationService,
    RoutingLifecycleService,
)
from datamind.services.errors import IdentityError
from datamind.services.mutation import MutationResult
from datamind.utils import (
    generate_random_id,
    get_hostname,
)


_STATIC_DIR = Path(__file__).parent / "dist"
_MAX_MODEL_UPLOAD_MB = 200
_MAX_MODEL_UPLOAD_BYTES = _MAX_MODEL_UPLOAD_MB * MB
_CAPABILITY_PERMISSIONS = {
    "models.create": "model.write",
    "versions.manage": "model.write",
    "deployments.create": "deployment.write",
    "deployments.manage": "deployment.write",
    "deployments.delete": "deployment.delete",
    "routings.create": "routing.write",
    "routings.manage": "routing.write",
    "routings.delete": "routing.delete",
    "experiments.create": "experiment.write",
    "experiments.manage": "experiment.write",
    "experiments.delete": "experiment.delete",
    "variants.create": "experiment.write",
    "variants.manage": "experiment.write",
    "variants.delete": "experiment.delete",
    "users.create": "identity.manage",
    "users.manage": "identity.manage",
    "roles.create": "identity.manage",
    "roles.manage": "identity.manage",
    "runtimes.manage": "runtime.manage",
}
_EVENT_BATCH_SIZE = 200
_EVENT_HEARTBEAT_SECONDS = 15
_EVENT_AUTH_CHECK_SECONDS = 60
_EXPORT_PAGE_SIZE = 100
_EXPORT_MAX_ROWS = 10_000
_EventQueryResult = TypeVar(
    "_EventQueryResult"
)

logger = structlog.get_logger(__name__)


_security_headers_middleware = security_headers


async def _health(
        _request: Request,
) -> JSONResponse:
    """返回管理控制台健康状态"""
    return JSONResponse({
        "status": "ok",
    })


async def _page(
        request: Request,
) -> Response:
    """返回管理控制台页面"""
    static_files = ConsoleStaticFiles(
        directory=_STATIC_DIR,
        check_dir=False,
    )
    try:
        return await static_files.get_response("index.html", request.scope)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        return PlainTextResponse(
            "控制台静态资源尚未构建，请在项目根目录运行 npm ci 和 npm run build:console。",
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )


async def _login(
        request: Request,
) -> JSONResponse:
    """使用本地账户创建浏览器会话"""
    attempted_username = await _requested_login_username(
        request
    )
    response = await browser_auth.login(
        request,
        unit_of_work=UnitOfWork,
        auth_service=create_auth_service,
        user_payload=_user_payload,
        client_ip=_client_ip,
        error_response=_error_response,
        set_session_cookies=browser_cookies.set_session_cookies,
    )
    successful = response.status_code < 400
    authenticated_user = getattr(
        request.state,
        "authenticated_user",
        None,
    )
    await _record_authentication_event(
        request,
        action="auth.login",
        actor_username=(
            authenticated_user.username
            if isinstance(
                authenticated_user,
                AuthenticatedUser,
            )
            else "anonymous"
        ),
        attempted_username=(
            attempted_username
            if not successful
            else None
        ),
        target_id=(
            authenticated_user.user_id
            if isinstance(
                authenticated_user,
                AuthenticatedUser,
            )
            else "unknown"
        ),
        successful=successful,
        status_code=response.status_code,
        error=(
            None
            if successful
            else "登录失败"
        ),
    )
    return response


async def _refresh(
        request: Request,
) -> Response:
    """轮换浏览器登录凭据"""
    response = await browser_auth.refresh(
        request,
        refresh_cookie=browser_cookies.REFRESH_COOKIE,
        unit_of_work=UnitOfWork,
        auth_service=create_auth_service,
        client_ip=_client_ip,
        error_response=_error_response,
        set_session_cookies=browser_cookies.set_session_cookies,
        clear_session_cookies=browser_cookies.clear_session_cookies,
    )

    if response.status_code >= 400:
        if response.status_code == 401:
            if request.cookies.get(browser_cookies.REFRESH_COOKIE) is None:
                return response

            log = logger.info
            message = "控制台会话已失效，需要重新登录"
        elif response.status_code >= 500:
            log = logger.error
            message = "控制台会话续期异常，认证服务暂不可用"
        else:
            log = logger.warning
            message = "控制台会话续期失败"

        log(
            message,
            status_code=response.status_code,
            **_http_actor_context(
                request,
                username="unknown",
            ),
        )

    return response


async def _logout(
        request: Request,
) -> Response:
    """撤销浏览器会话"""
    user = await _authenticate(
        request
    )
    response = await browser_auth.logout(
        request,
        refresh_cookie=browser_cookies.REFRESH_COOKIE,
        unit_of_work=UnitOfWork,
        auth_service=create_auth_service,
        clear_session_cookies=browser_cookies.clear_session_cookies,
    )
    revocation_failed = bool(
        getattr(
            request.state,
            "logout_revocation_failed",
            False,
        )
    )
    logout_result = getattr(
        request.state,
        "logout_result",
        None,
    )
    result_identity = (
        logout_result
        if isinstance(
            logout_result,
            LogoutResult,
        )
        else None
    )
    actor_username = "anonymous"
    target_id = "unknown"

    if user is not None:
        actor_username = user.username
        target_id = user.user_id
    elif result_identity is not None:
        actor_username = (
            result_identity.username
            or result_identity.user_id
            or actor_username
        )
        target_id = (
            result_identity.user_id
            or target_id
        )

    await _record_authentication_event(
        request,
        action="auth.logout",
        actor_username=actor_username,
        target_id=target_id,
        successful=not revocation_failed,
        status_code=response.status_code,
        error=(
            "刷新令牌撤销失败"
            if revocation_failed
            else None
        ),
        details=(
            {
                "revoked": result_identity.revoked,
            }
            if result_identity is not None
            else None
        ),
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

    response = JSONResponse(
        _user_payload(user)
    )
    browser_cookies.ensure_csrf_cookie(
        response=response,
        request=request,
    )
    return response


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

    trend_range = request.query_params.get(
        "range",
        "24h",
    )

    try:
        snapshot = await DashboardService().snapshot(
            permissions=user.permissions,
            trend_range=trend_range,
        )
    except ValueError as exc:
        return _error_response(
            str(exc),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "控制台数据暂不可用",
            status_code=503,
        )

    return JSONResponse(
        snapshot
    )


async def _management_options(
        request: Request,
) -> JSONResponse:
    """返回资源管理表单使用的可选项"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    can_manage_identity = has_permission(
        granted_permissions=user.permissions,
        required_permission="identity.manage",
    )
    roles: list[dict[str, Any]] = []

    if can_manage_identity:
        try:
            role_records = await IdentityService().list_roles(
                status=RoleStatus.ACTIVE,
                limit=1000,
            )
        except (
                IdentityError,
                SQLAlchemyError,
        ):
            return _error_response(
                "身份管理选项暂不可用",
                status_code=503,
            )

        roles = [
            {
                "name": role["name"],
                "description": role.get("description"),
            }
            for role in role_records
        ]

    return JSONResponse({
        "model_types": (
            sorted(SUPPORTED_MODEL_TYPES)
            if has_permission(
                granted_permissions=user.permissions,
                required_permission="model.write",
            )
            else []
        ),
        "permissions": (
            [
                "*",
                *sorted(SUPPORTED_PERMISSIONS),
            ]
            if can_manage_identity
            else []
        ),
        "roles": roles,
        "routing_rules": {
            "schema": RoutingRules.model_json_schema(),
            "example": ROUTING_RULES_EXAMPLE,
        },
    })


async def _model_registration_target(
        request: Request,
) -> JSONResponse:
    """查询模型及指定版本是否已存在"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

    if not has_permission(
            granted_permissions=user.permissions,
            required_permission="model.write",
    ):
        return _error_response(
            "没有执行该操作的权限",
            status_code=403,
        )

    name = request.query_params.get(
        "name",
        "",
    ).strip()
    version = request.query_params.get(
        "version",
        "",
    ).strip()

    if not name:
        return JSONResponse({
            "exists": False,
            "description": None,
            "version_exists": False,
        })

    try:
        async with UnitOfWork() as uow:
            model = await MetadataRepository(
                uow.session
            ).get_model(
                name=name,
            )
            versions = (
                await VersionRepository(
                    uow.session
                ).list_versions(
                    model_id=model.model_id,
                    version=version,
                    include_archived=True,
                    limit=1,
                )
                if model is not None and version
                else []
            )
    except SQLAlchemyError:
        return _error_response(
            "模型信息暂不可用",
            status_code=503,
        )

    return JSONResponse({
        "exists": model is not None,
        "description": (
            model.description
            if model is not None
            else None
        ),
        "version_exists": bool(versions),
    })


async def _model_detail(
        request: Request,
) -> JSONResponse:
    """返回模型详情"""
    user = await _authenticate(request)

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
        result = await service.get_model_detail(
            model_id=request.path_params[
                "model_id"
            ],
        )
    except ValueError as validation_error:
        return _error_response(
            str(validation_error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "模型信息暂不可用",
            status_code=503,
        )

    if result is None:
        return _error_response(
            "模型不存在",
            status_code=404,
        )

    return JSONResponse(result)


async def _version_detail(
        request: Request,
) -> JSONResponse:
    """返回模型版本详情"""
    user = await _authenticate(request)

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
        result = await service.get_version_detail(
            version_id=request.path_params[
                "version_id"
            ],
        )
    except ValueError as validation_error:
        return _error_response(
            str(validation_error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "模型版本信息暂不可用",
            status_code=503,
        )

    if result is None:
        return _error_response(
            "模型版本不存在",
            status_code=404,
        )

    return JSONResponse(result)


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
        deleted = request.query_params.get(
            "deleted",
            "false",
        ).lower()
        if deleted not in {"true", "false"}:
            raise ValueError("deleted 只支持 true 或 false")
        result = await service.get_model_versions(
            model_id=request.path_params[
                "model_id"
            ],
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            deleted=deleted == "true",
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
        deleted = request.query_params.get(
            "deleted",
            "false",
        ).lower()
        if deleted not in {"true", "false"}:
            raise ValueError("deleted 只支持 true 或 false")
        result = await service.get_section(
            section=section,
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            deleted=deleted == "true",
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
        deleted = request.query_params.get(
            "deleted",
            "false",
        ).lower()
        if deleted not in {"true", "false"}:
            raise ValueError("deleted 只支持 true 或 false")
        result = await service.get_experiment_variants(
            experiment_id=request.path_params[
                "experiment_id"
            ],
            page=page,
            page_size=page_size,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            **({"deleted": True} if deleted == "true" else {}),
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


async def _section_export(
        request: Request,
) -> Response:
    """导出控制台页面查询结果"""
    return await _export_records(
        request=request,
        section=request.path_params[
            "section"
        ],
    )


async def _model_versions_export(
        request: Request,
) -> Response:
    """导出指定模型的版本查询结果"""
    return await _export_records(
        request=request,
        section="versions",
        model_id=request.path_params[
            "model_id"
        ],
    )


async def _experiment_variants_export(
        request: Request,
) -> Response:
    """导出指定实验的分组查询结果"""
    return await _export_records(
        request=request,
        section="variants",
        experiment_id=request.path_params[
            "experiment_id"
        ],
    )


async def _export_records(
        *,
        request: Request,
        section: str,
        model_id: str | None = None,
        experiment_id: str | None = None,
) -> Response:
    """校验权限并流式导出当前查询结果"""
    user = await _authenticate(
        request
    )

    if user is None:
        return _error_response(
            "尚未登录",
            status_code=401,
        )

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

    if not has_permission(
            granted_permissions=user.permissions,
            required_permission="data.export",
    ):
        return _error_response(
            "没有数据导出权限",
            status_code=403,
        )

    try:
        record_ids = await _get_export_record_ids(
            request
        )
    except ValueError as error:
        return _error_response(
            str(error),
            status_code=400,
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
    deleted = request.query_params.get(
        "deleted",
        "false",
    ).lower() == "true"
    async def load_page(
            page: int,
    ) -> dict[str, Any]:
        selection_arguments = (
            {
                "record_ids": record_ids,
            }
            if record_ids is not None
            else {}
        )

        if model_id is not None:
            return await service.get_model_versions(
                model_id=model_id,
                page=page,
                page_size=_EXPORT_PAGE_SIZE,
                query=query,
                sort_by=sort_by,
                sort_order=sort_order,
                deleted=deleted,
                **selection_arguments,
            )

        if experiment_id is not None:
            return await service.get_experiment_variants(
                experiment_id=experiment_id,
                page=page,
                page_size=_EXPORT_PAGE_SIZE,
                query=query,
                sort_by=sort_by,
                sort_order=sort_order,
                **({"deleted": True} if deleted else {}),
                **selection_arguments,
            )

        return await service.get_section(
            section=section,
            page=page,
            page_size=_EXPORT_PAGE_SIZE,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            deleted=deleted,
            **selection_arguments,
        )

    try:
        first_page = await load_page(
            1
        )
    except ValueError as error:
        return _error_response(
            str(error),
            status_code=400,
        )
    except SQLAlchemyError:
        return _error_response(
            "导出数据暂不可用",
            status_code=503,
        )

    total = int(
        first_page["total"]
    )

    if record_ids is not None and total == 0:
        return _error_response(
            "所选记录不存在或已不在当前查询范围",
            status_code=400,
        )

    if total > _EXPORT_MAX_ROWS:
        return _error_response(
            "导出结果超过 10000 条，请缩小查询范围",
            status_code=400,
        )

    target_id = (
        model_id
        or experiment_id
        or section
    )
    await AuditRecorder().record(
        action="console.export",
        target_type="console",
        target_id=target_id,
        after={
            "section": section,
            "query": query,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "total": total,
            "selection": (
                "selected"
                if record_ids is not None
                else "query"
            ),
        },
        context=_http_audit_context(
            request,
            user=user,
        ),
    )

    filename = _export_filename(
        section
    )

    return StreamingResponse(
        _stream_csv_export(
            first_page=first_page,
            load_page=load_page,
        ),
        media_type="text/csv",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
        },
    )


async def _get_export_record_ids(
        request: Request,
) -> tuple[str, ...] | None:
    """读取导出请求中选择的记录 ID"""
    if request.method != "POST":
        return None

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(
            "导出请求格式无效"
        ) from error

    if not isinstance(body, dict):
        raise ValueError(
            "导出请求格式无效"
        )

    values = body.get(
        "record_ids"
    )

    if not isinstance(values, list):
        raise ValueError(
            "record_ids 必须是数组"
        )

    if any(
            not isinstance(value, str)
            for value in values
    ):
        raise ValueError(
            "record_ids 只能包含字符串"
        )

    return tuple(
        values
    )


async def _stream_csv_export(
        *,
        first_page: dict[str, Any],
        load_page: Callable[
            [int],
            Awaitable[dict[str, Any]],
        ],
) -> AsyncIterator[str]:
    """按页生成 UTF-8 CSV 内容"""
    yield "\ufeff"
    page_data = first_page
    fieldnames = list(
        page_data["items"][0].keys()
    ) if page_data["items"] else []

    if not fieldnames:
        return

    yield _encode_csv_row(
        fieldnames,
        dict.fromkeys(
            fieldnames,
            None,
        ),
        header=True,
    )

    while True:
        for item in page_data["items"]:
            yield _encode_csv_row(
                fieldnames,
                item,
            )

        if not page_data["has_next"]:
            return

        page_data = await load_page(
            int(page_data["page"]) + 1
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
                visible_events = [
                    event
                    for event in events
                    if event.topic in allowed_topics
                ]
                topics = sorted({
                    event.topic
                    for event in visible_events
                })

                yield _encode_sse(
                    event=(
                        "changed"
                        if topics
                        else "cursor"
                    ),
                    event_id=cursor,
                    data={
                        "topics": topics,
                        "changes": [
                            {
                                "topic": event.topic,
                                "action": event.action,
                            }
                            for event in visible_events
                        ],
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
    return await _complete_event_query(
        _query_event_window()
    )


async def _query_event_window() -> tuple[int | None, int]:
    """查询当前可回放事件游标范围"""
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
    return await _complete_event_query(
        _query_events_after(
            event_id
        )
    )


async def _query_events_after(
        event_id: int,
) -> list[OutboxEvent]:
    """查询指定游标之后的一批事件"""
    async with UnitOfWork() as uow:
        return await OutboxRepository(
            uow.session
        ).list_events(
            after_event_id=event_id,
            limit=_EVENT_BATCH_SIZE,
        )


async def _complete_event_query(
        query: Coroutine[
            Any,
            Any,
            _EventQueryResult,
        ],
) -> _EventQueryResult:
    """在请求取消时等待事件查询完成数据库清理"""
    query_task = asyncio.create_task(
        query
    )

    try:
        return await asyncio.shield(
            query_task
        )
    except asyncio.CancelledError as cancellation:
        while not query_task.done():
            try:
                await asyncio.shield(
                    query_task
                )
            except asyncio.CancelledError:
                continue

        query_task.result()
        raise cancellation


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


async def _authorize_write(
        request: Request,
        *,
        permission: str | None = None,
) -> tuple[AuthenticatedUser | None, JSONResponse | None]:
    """校验控制台写操作的身份、可选权限与 CSRF 令牌"""
    user = await _authenticate(
        request
    )

    if user is None:
        return None, _error_response(
            "尚未登录",
            status_code=401,
        )

    if (
            permission is not None
            and not has_permission(
                granted_permissions=user.permissions,
                required_permission=permission,
            )
    ):
        return None, _error_response(
            "没有执行该操作的权限",
            status_code=403,
        )

    cookie_token = request.cookies.get(
        browser_cookies.CSRF_COOKIE
    )
    header_token = request.headers.get(
        "x-csrf-token"
    )

    if (
            cookie_token is None
            or header_token is None
            or not secrets.compare_digest(
                cookie_token,
                header_token,
            )
    ):
        return None, _error_response(
            "请求安全校验失败，请刷新页面后重试",
            status_code=403,
        )

    origin = request.headers.get(
        "origin"
    )
    expected_origin = (
        f"{request.url.scheme}://{request.url.netloc}"
    )

    if origin is not None and origin != expected_origin:
        return None, _error_response(
            "请求来源不受信任",
            status_code=403,
        )

    return user, None


async def _requested_login_username(
        request: Request,
) -> str:
    """读取登录用户名，不保留请求中的认证秘密"""
    try:
        payload = await request.json()
    except (
            json.JSONDecodeError,
            UnicodeDecodeError,
    ):
        return "unknown"

    if not isinstance(payload, dict):
        return "unknown"

    username = payload.get("username")

    if not isinstance(username, str):
        return "unknown"

    normalized = username.strip()
    return normalized[:64] or "unknown"


def _http_actor_context(
        request: Request,
        *,
        username: str = "unknown",
) -> dict[str, object]:
    """构建可信的控制台 HTTP 操作人上下文"""
    return {
        USER: username,
        SOURCE: AuditSource.HTTP,
        IP: _client_ip(request),
        REQUEST_ID: _http_request_id(request),
        TRACE_ID: _http_trace_id(request),
        HOSTNAME: get_hostname(),
    }


def _http_audit_context(
        request: Request,
        *,
        user: AuthenticatedUser,
) -> dict[str, object]:
    """构建已认证用户的控制台 HTTP 审计上下文"""
    return _http_actor_context(
        request,
        username=user.username,
    )


def _http_request_id(
        request: Request,
) -> str:
    """读取可信长度的请求 ID，缺失时生成新 ID"""
    cached = getattr(
        request.state,
        "audit_request_id",
        None,
    )

    if isinstance(cached, str):
        return cached

    request_id = request.headers.get(
        "x-request-id",
        "",
    ).strip()

    if not request_id or len(request_id) > 64:
        request_id = generate_random_id(
            prefix="req"
        )

    request.state.audit_request_id = request_id
    return request_id


def _http_trace_id(
        request: Request,
) -> str:
    """读取 W3C 追踪 ID，缺失或无效时生成新 ID"""
    cached = getattr(
        request.state,
        "audit_trace_id",
        None,
    )

    if isinstance(cached, str):
        return cached

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

    if not is_valid_trace_id(trace_id):
        trace_id = generate_trace_id()

    request.state.audit_trace_id = trace_id
    return trace_id


async def _record_write_audit(
        request: Request,
        *,
        user: AuthenticatedUser,
        action: str,
        target_type: str,
        target_id: str,
        result: dict[str, Any],
) -> None:
    """记录控制台写操作审计"""
    before = None
    after = result
    if isinstance(result, MutationResult):
        before = result.before
        after = result.after

    await AuditRecorder().record(
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        context=_http_audit_context(
            request,
            user=user,
        ),
    )


def _identity_service_for_request(
        request: Request,
        *,
        user: AuthenticatedUser,
) -> IdentityService:
    """创建携带可信 HTTP 审计上下文的身份服务"""
    return IdentityService(
        audit_source=AuditSource.HTTP,
        audit_context=_http_audit_context(
            request,
            user=user,
        ),
    )


async def _record_authentication_event(
        request: Request,
        *,
        action: str,
        actor_username: str,
        attempted_username: str | None = None,
        target_id: str,
        successful: bool,
        status_code: int,
        error: str | None,
        details: dict[str, object] | None = None,
) -> None:
    """记录不包含认证秘密的控制台认证事件"""
    context = _http_actor_context(
        request,
        username=actor_username,
    )
    await record_authentication_event(
        logger=logger,
        recorder=AuditRecorder(),
        channel="控制台",
        action=action,
        actor_username=actor_username,
        target_id=target_id,
        successful=successful,
        status_code=status_code,
        context=context,
        attempted_username=attempted_username,
        error=error,
        details=details,
    )


def _write_error_response(
        error: Exception,
) -> JSONResponse:
    """转换控制台写操作异常"""
    if isinstance(
            error,
            ValidationError,
    ):
        message = error.errors()[0].get(
            "msg",
            "请求参数无效",
        )
        return _error_response(
            str(message),
            status_code=400,
        )

    if isinstance(
            error,
            (
                IdentityError,
                ModelError,
                ExperimentError,
            ),
    ):
        return _error_response(
            str(error),
            status_code=409,
        )

    if isinstance(
            error,
            (ValueError, json.JSONDecodeError),
    ):
        return _error_response(
            str(error),
            status_code=400,
        )

    if isinstance(
            error,
            SQLAlchemyError,
    ):
        return _error_response(
            "管理操作暂不可用",
            status_code=503,
        )

    if isinstance(
            error,
            OSError,
    ):
        return _error_response(
            "上传文件处理失败",
            status_code=400,
        )

    return _error_response(
        "管理操作执行失败",
        status_code=500,
    )


def _service_environment(
) -> str:
    """返回当前控制台实例管理的唯一环境。"""
    return str(
        get_settings().service.environment
    )


# 资源创建处理器


async def _create_model(
        request: Request,
) -> JSONResponse:
    """上传模型文件并注册模型版本"""
    user, denied = await _authorize_write(
        request,
        permission="model.write",
    )

    if denied is not None or user is None:
        return denied or _error_response(
            "尚未登录",
            status_code=401,
        )

    try:
        form = await request.form(
            max_files=1,
            max_fields=2,
            max_part_size=_MAX_MODEL_UPLOAD_BYTES,
        )
        raw_metadata = form.get(
            "metadata"
        )
        upload = form.get(
            "file"
        )

        if not isinstance(raw_metadata, str):
            raise ValueError(
                "缺少模型注册参数"
            )

        if not isinstance(upload, UploadFile):
            raise ValueError(
                "请选择模型文件"
            )

        metadata = ModelRegistrationMetadata.model_validate_json(
            raw_metadata
        )

        suffix = Path(
            upload.filename or "model.bin"
        ).suffix[:20]

        with tempfile.TemporaryDirectory(
                prefix="datamind-console-"
        ) as directory:
            model_path = Path(directory) / (
                f"model{suffix}"
            )
            written = 0

            with model_path.open("wb") as stream:
                while chunk := await upload.read(
                        1024 * 1024
                ):
                    written += len(chunk)

                    if written > _MAX_MODEL_UPLOAD_BYTES:
                        raise ValueError(
                            "模型文件不能超过 "
                            f"{_MAX_MODEL_UPLOAD_MB} MB"
                        )

                    stream.write(chunk)

            if written == 0:
                raise ValueError(
                    "模型文件不能为空"
                )

            result = await ModelRegistrationService().register(
                **metadata.model_dump(),
                model_path=str(model_path),
                created_by=user.username,
            )

        await _record_write_audit(
            request,
            user=user,
            action="model.register",
            target_type="model",
            target_id=str(result["model_id"]),
            result=result,
        )
        return JSONResponse(
            result,
            status_code=201,
        )
    except (
            ValidationError,
            ValueError,
            ModelError,
            SQLAlchemyError,
            OSError,
            json.JSONDecodeError,
    ) as error:
        return _write_error_response(
            error
        )


async def _create_deployment(
        request: Request,
) -> JSONResponse:
    """创建模型部署"""
    user, denied = await _authorize_write(
        request,
        permission="deployment.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = DeploymentCreateRequest.model_validate(
            await request.json()
        )
        result = await DeploymentLifecycleService().create_deployment(
            **payload.model_dump(),
            environment=_service_environment(),
            deployed_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="deployment.create",
            target_type="deployment",
            target_id=str(result["deployment_id"]),
            result=result,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            ModelError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _create_routing(
        request: Request,
) -> JSONResponse:
    """创建路由规则"""
    user, denied = await _authorize_write(
        request,
        permission="routing.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = RoutingCreateRequest.model_validate(
            await request.json()
        )
        result = await RoutingLifecycleService().create_routing(
            **payload.model_dump(),
            environment=_service_environment(),
            created_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="route.create",
            target_type="routing",
            target_id=str(result["routing_id"]),
            result=result,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _create_experiment(
        request: Request,
) -> JSONResponse:
    """创建实验"""
    user, denied = await _authorize_write(
        request,
        permission="experiment.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = ExperimentCreateRequest.model_validate(
            await request.json()
        )
        result = await ExperimentLifecycleService().create_experiment(
            **payload.model_dump(),
            environment=_service_environment(),
            created_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="experiment.create",
            target_type="experiment",
            target_id=str(result["experiment_id"]),
            result=result,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            ExperimentError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _create_variant(
        request: Request,
) -> JSONResponse:
    """创建实验分组"""
    user, denied = await _authorize_write(
        request,
        permission="experiment.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = VariantCreateRequest.model_validate(
            await request.json()
        )
        result = await ExperimentLifecycleService().create_variant(
            experiment_id=request.path_params["experiment_id"],
            **payload.model_dump(),
            created_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="experiment.variant.create",
            target_type="variant",
            target_id=str(result["variant_id"]),
            result=result,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            ExperimentError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _create_user(
        request: Request,
) -> JSONResponse:
    """创建本地用户"""
    user, denied = await _authorize_write(
        request,
        permission="identity.manage",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = UserCreateRequest.model_validate(
            await request.json()
        )
        values = payload.model_dump()
        roles = values.pop("roles")
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.create_user(
            **values,
            role_names=roles,
            operator_id=user.user_id,
            operator=user.username,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _create_role(
        request: Request,
) -> JSONResponse:
    """创建角色"""
    user, denied = await _authorize_write(
        request,
        permission="identity.manage",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = RoleCreateRequest.model_validate(
            await request.json()
        )
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.create_role(
            **payload.model_dump(),
            operator_id=user.user_id,
            operator=user.username,
        )
        return JSONResponse(result, status_code=201)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


# 资源更新处理器


async def _update_model(
        request: Request,
) -> JSONResponse:
    """更新模型显示名称和描述"""
    user, denied = await _authorize_write(
        request,
        permission="model.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = ModelUpdateRequest.model_validate(
            await request.json()
        )
        result = await ModelCatalogService().update_model(
            model_id=request.path_params["model_id"],
            **payload.model_dump(),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="model.update",
            target_type="model",
            target_id=str(result["model_id"]),
            result=result,
        )
        updated_at = result.get("updated_at")
        response_result = {
            **result,
            "updated_at": (
                updated_at.isoformat()
                if isinstance(updated_at, datetime)
                else updated_at
            ),
        }
        return JSONResponse(response_result)
    except (
            ValidationError,
            ValueError,
            ModelError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _update_version(
        request: Request,
) -> JSONResponse:
    """更新模型版本说明"""
    user, denied = await _authorize_write(
        request,
        permission="model.write",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = VersionUpdateRequest.model_validate(
            await request.json()
        )
        result = await ModelCatalogService().update_version(
            version_id=request.path_params["version_id"],
            **payload.model_dump(),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="model.version.update",
            target_type="version",
            target_id=str(result["version_id"]),
            result=result,
        )
        updated_at = result.get("updated_at")
        return JSONResponse({
            **result,
            "updated_at": (
                updated_at.isoformat()
                if isinstance(updated_at, datetime)
                else updated_at
            ),
        })
    except (
            ValidationError,
            ValueError,
            ModelError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _update_deployment(request: Request) -> JSONResponse:
    """更新模型部署"""
    user, denied = await _authorize_write(
        request,
        permission="deployment.write",
    )
    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = DeploymentUpdateRequest.model_validate(
            await request.json()
        )
        result = await DeploymentLifecycleService().update_deployment(
            deployment_id=request.path_params["deployment_id"],
            **payload.model_dump(exclude_unset=True),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="deployment.update",
            target_type="deployment",
            target_id=str(result["deployment_id"]),
            result=result,
        )
        return JSONResponse(result)
    except (ValidationError, ValueError, ModelError, SQLAlchemyError) as error:
        return _write_error_response(error)


async def _update_routing(request: Request) -> JSONResponse:
    """更新路由规则"""
    user, denied = await _authorize_write(
        request,
        permission="routing.write",
    )
    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = RoutingUpdateRequest.model_validate(await request.json())
        result = await RoutingLifecycleService().update_routing(
            routing_id=request.path_params["routing_id"],
            **payload.model_dump(exclude_unset=True),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="routing.update",
            target_type="routing",
            target_id=str(result["routing_id"]),
            result=result,
        )
        return JSONResponse(result)
    except (ValidationError, ValueError, SQLAlchemyError) as error:
        return _write_error_response(error)


async def _update_experiment(request: Request) -> JSONResponse:
    """更新草稿实验"""
    user, denied = await _authorize_write(
        request,
        permission="experiment.write",
    )
    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = ExperimentUpdateRequest.model_validate(await request.json())
        result = await ExperimentLifecycleService().update_experiment(
            experiment_id=request.path_params["experiment_id"],
            **payload.model_dump(exclude_unset=True),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="experiment.update",
            target_type="experiment",
            target_id=str(result["experiment_id"]),
            result=result,
        )
        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            ExperimentError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _update_variant(request: Request) -> JSONResponse:
    """更新实验分组"""
    user, denied = await _authorize_write(
        request,
        permission="experiment.write",
    )
    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = VariantUpdateRequest.model_validate(await request.json())
        result = await ExperimentLifecycleService().update_variant(
            variant_id=request.path_params["variant_id"],
            **payload.model_dump(exclude_unset=True),
            updated_by=user.username,
        )
        await _record_write_audit(
            request,
            user=user,
            action="experiment.variant.update",
            target_type="variant",
            target_id=str(result["variant_id"]),
            result=result,
        )
        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            ExperimentError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _update_user(
        request: Request,
) -> JSONResponse:
    """更新用户资料"""
    user, denied = await _authorize_write(
        request,
        permission="identity.manage",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = UserUpdateRequest.model_validate(
            await request.json()
        )
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.update_user(
            username=request.path_params["username"],
            new_username=payload.username,
            display_name=payload.display_name,
            email=payload.email,
            role_names=payload.roles,
            operator_id=user.user_id,
            operator=user.username,
        )
        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _update_role(
        request: Request,
) -> JSONResponse:
    """更新角色权限"""
    user, denied = await _authorize_write(
        request,
        permission="identity.manage",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = RoleUpdateRequest.model_validate(
            await request.json()
        )
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.update_role(
            name=request.path_params["name"],
            description=payload.description,
            permissions=payload.permissions,
            operator_id=user.user_id,
            operator=user.username,
        )
        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)

async def _change_password(
        request: Request,
) -> JSONResponse:
    """修改当前用户密码并结束浏览器会话"""
    user, denied = await _authorize_write(
        request
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = PasswordChangeRequest.model_validate(
            await request.json()
        )
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.change_password(
            username=user.username,
            current_password=payload.current_password,
            new_password=payload.new_password,
            operator_id=user.user_id,
            operator=user.username,
        )
        response = JSONResponse(result)
        browser_cookies.clear_session_cookies(
            response
        )
        return response
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _reset_user_password(
        request: Request,
) -> JSONResponse:
    """重置用户密码"""
    user, denied = await _authorize_write(
        request,
        permission="identity.manage",
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    try:
        payload = PasswordResetRequest.model_validate(
            await request.json()
        )
        identity_service = _identity_service_for_request(
            request,
            user=user,
        )
        result = await identity_service.reset_password(
            username=request.path_params["username"],
            password=payload.password,
            operator_id=user.user_id,
            operator=user.username,
        )
        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)


async def _resource_action(
        request: Request,
) -> JSONResponse:
    """执行部署、路由、实验、分组或身份管理操作"""
    resource = request.path_params["resource"]
    identifier = request.path_params["identifier"]
    action = request.path_params["action"]
    permission_map = {
        "models": "model.write",
        "deployments": (
            "deployment.delete"
            if action == "delete"
            else "deployment.write"
        ),
        "routings": (
            "routing.delete"
            if action == "delete"
            else "routing.write"
        ),
        "experiments": (
            "experiment.delete"
            if action == "delete"
            else "experiment.write"
        ),
        "variants": (
            "experiment.delete"
            if action == "delete"
            else "experiment.write"
        ),
        "users": "identity.manage",
        "roles": "identity.manage",
        "versions": "model.write",
    }
    permission = permission_map.get(resource)

    if permission is None:
        return _error_response(
            "不支持的管理资源",
            status_code=404,
        )

    user, denied = await _authorize_write(
        request,
        permission=permission,
    )

    if denied is not None or user is None:
        return denied or _error_response("尚未登录", status_code=401)

    authenticated_user: AuthenticatedUser = user

    try:
        body = await request.body()
        payload = ResourceActionRequest.model_validate(
            json.loads(body)
            if body
            else {}
        )
        result = await dispatch_resource_action(
            resource=resource,
            identifier=identifier,
            action=action,
            reason=payload.reason,
            user_id=authenticated_user.user_id,
            username=authenticated_user.username,
            model_lifecycle_factory=ModelLifecycleService,
            model_deletion_factory=ModelDeletionService,
            deployment_factory=DeploymentLifecycleService,
            routing_factory=RoutingLifecycleService,
            experiment_factory=ExperimentLifecycleService,
            identity_factory=lambda **_kwargs: (
                _identity_service_for_request(
                    request,
                    user=authenticated_user,
                )
            ),
        )

        if resource not in {"users", "roles"}:
            await _record_write_audit(
                request,
                user=authenticated_user,
                action=f"console.{resource}.{action}",
                target_type=resource.rstrip("s"),
                target_id=identifier,
                result=result,
            )

        return JSONResponse(result)
    except (
            ValidationError,
            ValueError,
            IdentityError,
            ModelError,
            ExperimentError,
            SQLAlchemyError,
    ) as error:
        return _write_error_response(error)

def _user_payload(
        user: AuthenticatedUser,
) -> dict[str, object]:
    """转换当前用户信息"""
    payload = user.model_dump(
        mode="json"
    )
    payload["capabilities"] = {
        capability: has_permission(
            granted_permissions=user.permissions,
            required_permission=permission,
        )
        for capability, permission in (
            _CAPABILITY_PERMISSIONS.items()
        )
    }
    payload["environment"] = _service_environment()

    return payload


async def _authenticate(
        request: Request,
) -> AuthenticatedUser | None:
    """认证浏览器访问令牌"""
    user = await browser_auth.authenticate(
        request,
        access_cookie=browser_cookies.ACCESS_COOKIE,
        unit_of_work=UnitOfWork,
        auth_service=create_auth_service,
    )

    if user is not None:
        update_context(user=user.username)

    return user


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


def _request_context_middleware(
        app: ASGIApp,
        /,
) -> ASGIApp:
    """创建控制台请求日志上下文中间件"""
    return RequestContextMiddleware(
        app,
        context_factory=_http_actor_context,
    )


console_app = Starlette(
    debug=False,
    lifespan=_lifespan,
    middleware=[
        Middleware(
            _request_context_middleware
        ),
        Middleware(
            _security_headers_middleware
        )
    ],
    routes=create_routes(
        ConsoleHandlers(
            health=_health,
            page=_page,
            login=_login,
            refresh=_refresh,
            logout=_logout,
            session=_session,
            overview=_overview,
            management_options=_management_options,
            model_registration_target=(
                _model_registration_target
            ),
            model_detail=_model_detail,
            version_detail=_version_detail,
            create_model=_create_model,
            update_model=_update_model,
            update_version=_update_version,
            create_deployment=_create_deployment,
            update_deployment=_update_deployment,
            create_routing=_create_routing,
            update_routing=_update_routing,
            create_experiment=_create_experiment,
            update_experiment=_update_experiment,
            create_user=_create_user,
            update_user=_update_user,
            create_role=_create_role,
            update_role=_update_role,
            change_password=_change_password,
            reset_user_password=_reset_user_password,
            resource_action=_resource_action,
            model_versions_export=_model_versions_export,
            model_versions=_model_versions,
            experiment_variants_export=(
                _experiment_variants_export
            ),
            create_variant=_create_variant,
            update_variant=_update_variant,
            experiment_variants=_experiment_variants,
            section_export=_section_export,
            section=_section,
            events=_events,
        ),
        static_dir=_STATIC_DIR,
    ),
)
