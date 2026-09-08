"""创建角色命令

提供角色和权限集合创建功能。

核心功能：
  - create_role: 创建角色

使用示例：
  python -m datamind.cli.main role create developer \
    --permission model.read \
    --permission model.write
"""

import asyncio
import json

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="创建角色命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("create")
def create_role(
        name: str = typer.Argument(
            ...,
            help="角色名称",
        ),
        permissions: list[str] | None = typer.Option(
            None,
            "--permission",
            help="权限标识，可重复指定",
        ),
        all_permissions: bool = typer.Option(
            False,
            "--all-permissions",
            help="授予全部权限",
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="角色说明",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """创建角色"""
    if all_permissions and permissions:
        raise typer.BadParameter(
            "--all-permissions 与 --permission 不能同时指定"
        )

    resolved_permissions = (
        [
            "*"
        ]
        if all_permissions
        else permissions or []
    )

    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始创建角色",
                name=name,
                permissions=resolved_permissions,
            )

            result = await IdentityService().create_role(
                name=name,
                permissions=resolved_permissions,
                description=description,
                operator_id=(
                    identity.user_id
                    if identity is not None
                    else context.user
                ),
                operator=context.user,
            )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
            )
            return

        permission_values = (
            ", ".join(
                result["permissions"]
            )
            or "-"
        )

        console.info("角色创建成功\n")
        console.print(
            f"{'NAME':<16} : "
            f"{result['name']}"
        )
        console.print(
            f"{'PERMISSIONS':<16} : "
            f"{permission_values}"
        )

    try:
        asyncio.run(
            runner()
        )
    except (
        IdentityError,
        ValueError,
    ) as exc:
        console.error(
            f"创建角色失败：{exc}",
            output_format=output,
            error_type=type(exc).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
