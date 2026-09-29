"""管理控制台路由表测试.

验证页面、接口和静态资源路由集中注册且方法约束准确。

核心功能：
  - test_create_routes_registers_expected_endpoints:
    验证控制台路由表
"""

from dataclasses import fields
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import (
    Mount,
    Route,
)

from datamind.console.routes import (
    ConsoleHandlers,
    create_routes,
)
from datamind.console.assets import ConsoleStaticFiles


async def handler(_request: Request) -> Response:
    """返回路由测试响应."""
    return Response()


def test_create_routes_registers_expected_endpoints() -> None:
    """测试路由表包含预期端点、方法和静态资源."""
    static_dir = (
        Path(__file__).parents[2]
        / "datamind"
        / "console"
        / "dist"
    )
    handlers = ConsoleHandlers(
        **{
            field.name: handler
            for field in fields(ConsoleHandlers)
        }
    )

    routes = create_routes(
        handlers,
        static_dir=static_dir,
    )
    http_routes = {
        route.path: route.methods
        for route in routes
        if isinstance(route, Route)
    }

    assert http_routes["/health"] == {"GET", "HEAD"}
    assert http_routes["/ready"] == {"GET", "HEAD"}
    assert http_routes["/api/models"] == {"POST"}
    assert http_routes[
        "/api/models/{model_id:str}/detail"
    ] == {"GET", "HEAD"}
    assert http_routes[
        "/api/versions/{version_id:str}/detail"
    ] == {"GET", "HEAD"}
    assert http_routes[
        "/api/models/{model_id:str}"
    ] == {"PATCH"}
    assert http_routes[
        "/api/sections/{section:str}/export"
    ] == {"GET", "HEAD", "POST"}
    assert http_routes["/api/events"] == {"GET", "HEAD"}

    static_route = next(
        route
        for route in routes
        if isinstance(route, Mount)
    )
    assert static_route.path == "/assets"
    assert static_route.name == "assets"
    assert isinstance(static_route.app, ConsoleStaticFiles)
    assert static_route.app.directory == static_dir / "assets"
