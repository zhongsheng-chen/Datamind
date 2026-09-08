"""CLI 品牌展示

提供长期运行命令共用的 Logo、版本信息和启动摘要。

核心功能：
  - get_app_version: 获取应用版本
  - build_bind_address: 构建服务监听地址
  - build_http_url: 构建本地访问地址
  - print_startup_summary: 打印启动摘要
  - print_http_server_summary: 打印 HTTP 服务启动摘要
"""

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlunsplit

from rich.console import Console

from datamind._build import BUILD_COMMIT


POWERED_BY = "Zhongsheng Chen"

LOGO = r"""
 ____        _                  _           _ 
|  _ \  __ _| |_ __ _ _ __ ___ (_)_ __   __| |
| | | |/ _` | __/ _` | '_ ` _ \| | '_ \ / _` |
| |_| | (_| | || (_| | | | | | | | | | | (_| |
|____/ \__,_|\__\__,_|_| |_| |_|_|_| |_|\__,_|
""".strip("\n")


def get_app_version() -> str:
    """获取应用版本号"""
    try:
        app_version = version(
            "datamind"
        )
    except PackageNotFoundError:
        app_version = "unknown"

    if BUILD_COMMIT != "dev":
        app_version = (
            f"{app_version} "
            f"({BUILD_COMMIT})"
        )

    return app_version


def build_http_url(
        *,
        host: str,
        port: int,
        path: str = "",
) -> str:
    """构建适合本机访问的 HTTP 地址"""
    display_host = (
        "127.0.0.1"
        if host in {
            "0.0.0.0",
            "::",
        }
        else host
    )
    netloc_host = (
        f"[{display_host}]"
        if ":" in display_host
        and not display_host.startswith("[")
        else display_host
    )

    return urlunsplit((
        "http",
        f"{netloc_host}:{port}",
        path,
        "",
        "",
    ))


def build_bind_address(
        *,
        host: str,
        port: int,
) -> str:
    """构建包含端口的服务监听地址"""
    displayed_host = (
        f"[{host}]"
        if ":" in host
        and not host.startswith("[")
        else host
    )

    return f"{displayed_host}:{port}"


def print_startup_summary(
        console: Console,
        details: Mapping[
            str,
            str | int | float | bool,
        ],
        *,
        app_version: str | None = None,
) -> None:
    """打印长期运行命令的启动摘要"""
    displayed_version = (
        app_version
        if app_version is not None
        else get_app_version()
    )
    console.print()
    console.print(
        LOGO,
        style="bold cyan",
    )
    console.print()
    console.print(
        "[bold]Datamind[/bold] "
        f"v{displayed_version} "
        f"[dim]· Powered by {POWERED_BY}[/dim]"
    )
    console.print()

    for label, value in details.items():
        console.print(
            f"{label:<16} : "
            f"{value}"
        )

    console.print()


def print_http_server_summary(
        console: Console,
        *,
        app_version: str,
        environment: str,
        bind_address: str,
        access_url: str,
        reload_enabled: bool,
        pid: int,
        workers: int | None = None,
) -> None:
    """打印 Datamind HTTP 服务的统一启动摘要"""
    details: dict[
        str,
        str | int | float | bool,
    ] = {
        "ENVIRONMENT": environment,
        "BIND": bind_address,
        "URL": access_url,
    }

    if workers is not None:
        details["WORKERS"] = workers

    details.update({
        "RELOAD": (
            "enabled"
            if reload_enabled
            else "disabled"
        ),
        "PID": pid,
    })

    print_startup_summary(
        console,
        details,
        app_version=app_version,
    )
