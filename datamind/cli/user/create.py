"""创建用户命令.

提供 LOCAL 用户创建和初始角色授予功能。

核心功能：
  - create_user: 创建用户

使用示例：
  python -m datamind.cli.main user create alice \
    --role viewer
"""

import asyncio
import json

import structlog
import typer
from datamind.cli.output import CLIConsole
from datamind.cli.organization import resolve_user_organization

from datamind.cli.common import cli_context
from datamind.services.identity import IdentityService
from datamind.services.errors import IdentityError


app = typer.Typer(help="创建用户命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("create")
def create_user(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
        display_name: str | None = typer.Option(
            None,
            "--display-name",
            help="用户显示名称",
        ),
        email: str | None = typer.Option(
            None,
            "--email",
            help="用户邮箱",
        ),
        employee_number: str | None = typer.Option(
            None,
            "--employee-number",
            help="工号",
        ),
        organization: str | None = typer.Option(
            None,
            "--organization",
            help="所属机构名称",
        ),
        organization_id: str | None = typer.Option(
            None,
            "--organization-id",
            help="所属机构 ID",
        ),
        department: str | None = typer.Option(
            None,
            "--department",
            help="所属部门名称",
        ),
        department_id: str | None = typer.Option(
            None,
            "--department-id",
            help="所属部门 ID",
        ),
        role_names: list[str] | None = typer.Option(
            None,
            "--role",
            help="初始角色，可重复指定",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """创建用户.

    部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。
    """
    password = typer.prompt(
        "用户密码",
        hide_input=True,
        confirmation_prompt="确认用户密码",
    )

    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            identity = context.authenticated_user

            logger.info(
                "开始创建用户",
                username=username,
                role_names=role_names or [],
            )

            profile_arguments = await resolve_user_organization(
                organization=organization,
                department=department,
                organization_id=organization_id,
                department_id=department_id,
            )

            if employee_number is not None:
                profile_arguments["employee_number"] = employee_number

            result = await IdentityService().create_user(
                username=username,
                password=password,
                display_name=display_name,
                email=email,
                **profile_arguments,
                role_names=role_names,
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

            roles = (
                ", ".join(
                    result["roles"]
                )
                or "-"
            )

            success_message = (
                "用户恢复成功"
                if result.get("action") == "restore"
                else "用户创建成功"
            )
            console.info(f"{success_message}\n")
            console.print(
                f"{'USER ID':<16} : "
                f"{result['user_id']}"
            )
            console.print(
                f"{'USERNAME':<16} : "
                f"{result['username']}"
            )
            console.print(
                f"{'ROLES':<16} : "
                f"{roles}"
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
            f"创建用户失败：{exc}",
            output_format=output,
            error_type=type(exc).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
