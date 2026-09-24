"""管理控制台路由.

集中定义页面、查询、管理操作、实时事件和静态资源路由。

核心功能：
  - create_routes: 创建控制台路由表
"""

from pathlib import Path
from collections.abc import (
    Awaitable,
    Callable,
)
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import (
    BaseRoute,
    Mount,
    Route,
)
from datamind.console.assets import ConsoleStaticFiles


RouteHandler = Callable[
    [Request],
    Awaitable[Response],
]


@dataclass(frozen=True, slots=True)
class ConsoleHandlers:
    """管理控制台路由处理器."""

    health: RouteHandler
    ready: RouteHandler
    page: RouteHandler
    login: RouteHandler
    refresh: RouteHandler
    logout: RouteHandler
    session: RouteHandler
    overview: RouteHandler
    management_options: RouteHandler
    model_registration_target: RouteHandler
    model_detail: RouteHandler
    version_detail: RouteHandler
    create_model: RouteHandler
    update_model: RouteHandler
    update_version: RouteHandler
    create_deployment: RouteHandler
    update_deployment: RouteHandler
    create_routing: RouteHandler
    update_routing: RouteHandler
    create_experiment: RouteHandler
    update_experiment: RouteHandler
    create_user: RouteHandler
    update_user: RouteHandler
    create_role: RouteHandler
    update_role: RouteHandler
    change_password: RouteHandler
    reset_user_password: RouteHandler
    resource_action: RouteHandler
    model_versions_export: RouteHandler
    model_versions: RouteHandler
    experiment_variants_export: RouteHandler
    create_variant: RouteHandler
    update_variant: RouteHandler
    experiment_variants: RouteHandler
    section_export: RouteHandler
    section: RouteHandler
    events: RouteHandler


def create_routes(
        handlers: ConsoleHandlers,
        *,
        static_dir: Path,
) -> list[BaseRoute]:
    """创建管理控制台路由表."""
    return [
        Route("/health", handlers.health, methods=["GET"]),
        Route("/ready", handlers.ready, methods=["GET"]),
        Route("/", handlers.page, methods=["GET"]),
        Route("/api/login", handlers.login, methods=["POST"]),
        Route("/api/refresh", handlers.refresh, methods=["POST"]),
        Route("/api/logout", handlers.logout, methods=["POST"]),
        Route("/api/session", handlers.session, methods=["GET"]),
        Route("/api/overview", handlers.overview, methods=["GET"]),
        Route(
            "/api/management/options",
            handlers.management_options,
            methods=["GET"],
        ),
        Route(
            "/api/models/registration-target",
            handlers.model_registration_target,
            methods=["GET"],
        ),
        Route(
            "/api/models/{model_id:str}/detail",
            handlers.model_detail,
            methods=["GET"],
        ),
        Route(
            "/api/versions/{version_id:str}/detail",
            handlers.version_detail,
            methods=["GET"],
        ),
        Route("/api/models", handlers.create_model, methods=["POST"]),
        Route(
            "/api/models/{model_id:str}",
            handlers.update_model,
            methods=["PATCH"],
        ),
        Route(
            "/api/versions/{version_id:str}",
            handlers.update_version,
            methods=["PATCH"],
        ),
        Route(
            "/api/deployments",
            handlers.create_deployment,
            methods=["POST"],
        ),
        Route(
            "/api/deployments/{deployment_id:str}",
            handlers.update_deployment,
            methods=["PATCH"],
        ),
        Route("/api/routings", handlers.create_routing, methods=["POST"]),
        Route(
            "/api/routings/{routing_id:str}",
            handlers.update_routing,
            methods=["PATCH"],
        ),
        Route(
            "/api/experiments",
            handlers.create_experiment,
            methods=["POST"],
        ),
        Route(
            "/api/experiments/{experiment_id:str}",
            handlers.update_experiment,
            methods=["PATCH"],
        ),
        Route("/api/users", handlers.create_user, methods=["POST"]),
        Route(
            "/api/users/{username:str}",
            handlers.update_user,
            methods=["PATCH"],
        ),
        Route("/api/roles", handlers.create_role, methods=["POST"]),
        Route(
            "/api/roles/{name:str}",
            handlers.update_role,
            methods=["PATCH"],
        ),
        Route(
            "/api/account/password",
            handlers.change_password,
            methods=["POST"],
        ),
        Route(
            "/api/users/{username:str}/reset-password",
            handlers.reset_user_password,
            methods=["POST"],
        ),
        Route(
            "/api/actions/{resource:str}/{identifier:str}/{action:str}",
            handlers.resource_action,
            methods=["POST"],
        ),
        Route(
            "/api/models/{model_id:str}/versions/export",
            handlers.model_versions_export,
            methods=["GET", "POST"],
        ),
        Route(
            "/api/models/{model_id:str}/versions",
            handlers.model_versions,
            methods=["GET"],
        ),
        Route(
            "/api/experiments/{experiment_id:str}/variants/export",
            handlers.experiment_variants_export,
            methods=["GET", "POST"],
        ),
        Route(
            "/api/experiments/{experiment_id:str}/variants",
            handlers.create_variant,
            methods=["POST"],
        ),
        Route(
            "/api/variants/{variant_id:str}",
            handlers.update_variant,
            methods=["PATCH"],
        ),
        Route(
            "/api/experiments/{experiment_id:str}/variants",
            handlers.experiment_variants,
            methods=["GET"],
        ),
        Route(
            "/api/sections/{section:str}/export",
            handlers.section_export,
            methods=["GET", "POST"],
        ),
        Route(
            "/api/sections/{section:str}",
            handlers.section,
            methods=["GET"],
        ),
        Route("/api/events", handlers.events, methods=["GET"]),
        Mount(
            "/assets",
            app=ConsoleStaticFiles(
                directory=static_dir / "assets",
                check_dir=False,
            ),
            name="assets",
        ),
    ]
