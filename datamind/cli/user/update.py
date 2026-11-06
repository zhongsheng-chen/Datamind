"""更新用户组织资料命令.

提供工号、所属机构和所属部门的修改功能，不改变用户名或角色。

核心功能：
  - update_user: 更新用户组织资料

使用示例：
  datamind user update alice --employee-number 001234 \
    --organization 总行 --department 人力资源部
"""

import asyncio
import json

import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.cli.organization import resolve_user_organization
from datamind.services.errors import IdentityError
from datamind.services.identity import IdentityService


app = typer.Typer(
    help="更新用户组织资料"
)
console = CLIConsole()


@app.command("update")
def update_user(
        username: str = typer.Argument(
            ...,
            help="登录用户名",
        ),
        employee_number: str | None = typer.Option(
            None,
            "--employee-number",
            help="工号，空字符串表示清空",
        ),
        organization: str | None = typer.Option(
            None,
            "--organization",
            help="所属机构名称",
        ),
        organization_id: str | None = typer.Option(
            None,
            "--organization-id",
            help="所属机构 ID，空字符串表示清空",
        ),
        department: str | None = typer.Option(
            None,
            "--department",
            help="所属部门名称",
        ),
        department_id: str | None = typer.Option(
            None,
            "--department-id",
            help="所属部门 ID，空字符串表示清空",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """更新已指定的组织资料字段，未指定字段保留原值.

    部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。
    """
    values = {
        "employee_number": employee_number,
        "organization_id": organization_id,
        "department_id": department_id,
    }
    profile: dict[str, str | None] = {
        key: value
        for key, value in values.items()
        if value is not None
    }
    if not profile and organization is None and department is None:
        raise typer.BadParameter(
            "请至少指定一项组织资料"
        )
    if output not in (
            "text",
            "json",
    ):
        raise typer.BadParameter(
            "--format 只支持 text 或 json"
        )

    async def runner() -> None:
        async with cli_context(
                required_permission="identity.manage",
        ) as context:
            service = IdentityService()
            current = await service.get_user(
                username=username
            )
            organization_values = await resolve_user_organization(
                organization=organization,
                department=department,
                organization_id=organization_id,
                department_id=department_id,
                current_organization_id=current.get(
                    "organization_id"
                ),
            )
            profile.update(
                organization_values
            )
            identity = context.authenticated_user
            result = await service.update_user(
                username=username,
                new_username=current["username"],
                display_name=current["display_name"],
                email=current["email"],
                organization_profile=profile,
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
            else:
                console.info(
                    "用户组织资料已更新"
                )

    try:
        asyncio.run(
            runner()
        )
    except (
            IdentityError,
            ValueError,
    ) as error:
        console.error(
            str(error),
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None
