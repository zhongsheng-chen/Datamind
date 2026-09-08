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

from datamind.auth.errors import AuthError
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole

console = CLIConsole()

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
                identity_verified=(
                    user is not None
                ),
            )
            console.info("当前登录身份\n")

            if user is None:
                console.print(
                    f"{'USERNAME':<16} : "
                    f"{result['username']}"
                )
                console.print(
                    f"{'AUTHENTICATION':<16} : "
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
                    f"{'USER ID':<16} : "
                    f"{result['user_id']}"
                )
                console.print(
                    f"{'USERNAME':<16} : "
                    f"{result['username']}"
                )
                console.print(
                    f"{'DISPLAY NAME':<16} : "
                    f"{result['display_name'] or '-'}"
                )
                console.print(
                    f"{'EMAIL':<16} : "
                    f"{result['email'] or '-'}"
                )
                console.print(
                    f"{'STATUS':<16} : "
                    f"{result['status']}"
                )
                console.print(
                    f"{'ROLES':<16} : "
                    f"{roles}"
                )
                console.print(
                    f"{'PERMISSIONS':<16} : "
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
        console.error(
            f"认证失败：{exc}",
        )
        raise typer.Exit(
            code=1
        ) from None
