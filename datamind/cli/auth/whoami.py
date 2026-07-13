# datamind/cli/auth/whoami.py

"""登录身份查询命令

提供当前 CLI 登录会话的身份查询功能。

核心功能：
  - whoami: 查询访问令牌对应的用户

使用示例：
  python -m datamind.cli.main whoami
"""

import asyncio
from typing import Any

import structlog
import typer
from rich.console import Console

from datamind.auth.errors import AuthError
from datamind.cli.common import cli_context

console = Console()

logger = structlog.get_logger(__name__)


def whoami() -> None:
    """查看当前登录用户"""
    async def runner() -> None:
        async with cli_context() as context:
            user = context.authenticated_user

            result: dict[str, Any] = (
                user.model_dump(
                    mode="json"
                )
                if user is not None
                else {
                    "username": context.user,
                    "authentication": "disabled",
                }
            )
            logger.info(
                "开始查询当前 CLI 身份",
                username=context.user,
                authentication_enabled=(
                    user is not None
                ),
            )

        console.print(
            "[green]当前登录身份[/green]\n"
        )

        if user is None:
            console.print(
                f"[cyan]{'USERNAME':<16}[/cyan] : "
                f"{result['username']}"
            )
            console.print(
                f"[cyan]{'AUTHENTICATION':<16}[/cyan] : "
                "未启用"
            )
        else:
            roles = (
                ", ".join(
                    result["roles"]
                )
                or "-"
            )
            permissions = (
                ", ".join(
                    result["permissions"]
                )
                or "-"
            )

            console.print(
                f"[cyan]{'USER ID':<16}[/cyan] : "
                f"{result['user_id']}"
            )
            console.print(
                f"[cyan]{'USERNAME':<16}[/cyan] : "
                f"{result['username']}"
            )
            console.print(
                f"[cyan]{'DISPLAY NAME':<16}[/cyan] : "
                f"{result['display_name'] or '-'}"
            )
            console.print(
                f"[cyan]{'EMAIL':<16}[/cyan] : "
                f"{result['email'] or '-'}"
            )
            console.print(
                f"[cyan]{'STATUS':<16}[/cyan] : "
                f"{result['status']}"
            )
            console.print(
                f"[cyan]{'ROLES':<16}[/cyan] : "
                f"{roles}"
            )
            console.print(
                f"[cyan]{'PERMISSIONS':<16}[/cyan] : "
                f"{permissions}"
            )

        logger.info(
            "当前 CLI 身份输出完成",
            username=result.get(
                "username"
            ),
        )

    try:
        asyncio.run(
            runner()
        )
    except AuthError as exc:
        console.print(
            f"[red]身份认证失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
