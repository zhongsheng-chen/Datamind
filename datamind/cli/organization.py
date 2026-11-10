"""机构与部门管理命令.

提供组织目录查询、创建、修改和删除功能，复用身份管理权限与审计组件。

命令组：
  - organization: 机构管理
  - department: 部门管理

核心功能：
  - resolve_user_organization: 将机构名称和部门路径解析为内部 ID

使用示例：
  datamind organization create 总行 --code HQ
  datamind department create 人力资源部 --organization 总行 --code HR
"""

import asyncio
import json
from typing import Any

import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.errors import IdentityError
from datamind.services.organization import OrganizationService


organization_app = typer.Typer(
    help="机构管理命令"
)
department_app = typer.Typer(
    help="部门管理命令"
)
console = CLIConsole()


async def _resolve_department_options(
        operation: str,
        values: dict[str, Any],
) -> dict[str, str | None]:
    """解析部门命令的机构和上级部门名称，服务层仍使用稳定 ID."""
    resolved = dict(
        values
    )
    organization = resolved.pop(
        "organization",
        None,
    )
    parent = resolved.pop(
        "parent",
        None,
    )
    parent_id = resolved.get(
        "parent_id"
    )
    if parent is not None and parent_id is not None:
        raise ValueError(
            "--parent 与 --parent-id 不能同时指定"
        )

    identifiers = await resolve_user_organization(
        organization=organization,
        organization_id=resolved.get("organization_id"),
        department=parent,
        department_id=parent_id,
    )
    resolved["organization_id"] = identifiers.get(
        "organization_id"
    )
    if operation == "save_department":
        if not resolved["organization_id"]:
            raise ValueError(
                "请指定 --organization 或 --organization-id"
            )
        resolved["parent_id"] = identifiers.get(
            "department_id"
        )
        reference = resolved.get("department_id")
        if isinstance(reference, str) and reference and not reference.startswith("dpt_"):
            target = await resolve_user_organization(
                organization_id=resolved["organization_id"],
                department=reference,
            )
            resolved["department_id"] = target["department_id"]

    return resolved


async def _resolve_department_delete_options(
        service: OrganizationService,
        values: dict[str, Any],
) -> dict[str, Any]:
    """解析待删除或变更状态的部门，并校验显式指定的所属机构."""
    values = dict(values)
    reference = values.pop("department")
    if not reference or not reference.strip():
        raise ValueError("部门名称、路径或 ID 不能为空")
    organization = values.pop("organization", None)
    organization_id = values.pop("organization_id", None)
    if reference.startswith("dpt_"):
        if organization is not None or organization_id is not None:
            selectors = await resolve_user_organization(
                organization=organization, organization_id=organization_id,
            )
            directory = await service.catalog()
            if not any(
                item["department_id"] == reference
                and item["organization_id"] == selectors.get("organization_id")
                for item in directory["departments"]
            ):
                raise ValueError("部门不存在或不属于该机构")
        values["department_id"] = reference
    else:
        if not organization and not organization_id:
            raise ValueError("指定部门名称前，请先指定所属机构")
        selectors = await resolve_user_organization(
            organization=organization,
            organization_id=organization_id,
            department=reference,
        )
        values["department_id"] = selectors["department_id"]

    return values


async def _execute(
        service: OrganizationService,
        operation: str,
        values: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    """执行组织查询或变更，查询时按需过滤所属机构."""
    if operation in (
            "departments",
            "save_department",
    ):
        values = await _resolve_department_options(
            operation,
            values,
        )

    if operation in ("save_organization", "delete_organization", "set_organization_active"):
        values = dict(values)
        reference = values.get("organization_id")
        if isinstance(reference, str) and reference and not reference.startswith("org_"):
            selectors = await resolve_user_organization(
                organization=reference
            )
            values["organization_id"] = selectors["organization_id"]

    if operation in ("delete_department", "set_department_active"):
        values = await _resolve_department_delete_options(service, values)

    if operation in ("save_organization", "save_department") and values.get("code") is None:
        values = dict(values)
        values.pop("code", None)

    if operation not in (
            "organizations",
            "departments",
    ):
        return await getattr(
            service,
            operation,
        )(**values)

    result = (await service.catalog())[operation]
    organization_id = values.get(
        "organization_id"
    )
    if organization_id:
        result = [
            item for item in result
            if item["organization_id"] == organization_id
        ]
    return result


def _run(
        operation: str,
        values: dict[str, Any],
        output: str,
        *,
        required_permission: str,
) -> None:
    """在已认证的 CLI 作用域中执行操作并输出组织信息."""
    if output not in (
            "text",
            "json",
    ):
        raise typer.BadParameter(
            "--format 只支持 text 或 json"
        )

    async def runner() -> None:
        async with cli_context(
                required_permission=required_permission,
        ):
            result = await _execute(
                OrganizationService(),
                operation,
                values,
            )
            if output == "json":
                console.print_json(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                    )
                )
                return

            items = result if isinstance(
                result,
                list,
            ) else [result]
            for item in items:
                identifier = (
                    item["department_id"]
                    if "department_id" in item
                    else item["organization_id"]
                )
                code = item.get(
                    "code"
                )
                code_suffix = (
                    f"  ({code})"
                    if isinstance(code, str) and code
                    else ""
                )

                console.print(
                    f"{identifier}  {item['name']}{code_suffix}"
                    + ("  [已停用]" if item.get("is_active") is False
                       else "  [上级已停用]" if item.get("is_available") is False else "")
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


@organization_app.command("list")
def list_organizations(
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """列出机构."""
    _run(
        "organizations",
        {},
        output,
        required_permission="identity.manage",
    )


@organization_app.command("create")
def create_organization(
        name: str = typer.Argument(
            ...,
            help="机构名称",
        ),
        code: str | None = typer.Option(
            None,
            "--code",
            help="机构业务编码（可选）",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """创建机构."""
    _run(
        "save_organization",
        {
            "code": code,
            "name": name,
        },
        output,
        required_permission="identity.manage",
    )


@organization_app.command("update")
def update_organization(
        organization: str = typer.Argument(
            ...,
            help="机构名称或 ID",
        ),
        code: str | None = typer.Option(
            None,
            "--code",
            help="机构编码",
        ),
        name: str = typer.Option(
            ...,
            "--name",
            help="机构名称",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """修改机构编码和名称."""
    _run(
        "save_organization",
        {
            "organization_id": organization,
            "code": code,
            "name": name,
        },
        output,
        required_permission="identity.manage",
    )


@department_app.command("list")
def list_departments(
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
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """列出部门."""
    _run(
        "departments",
        {
            "organization": organization,
            "organization_id": organization_id,
        },
        output,
        required_permission="identity.manage",
    )


@department_app.command("create")
def create_department(
        name: str = typer.Argument(
            ...,
            help="部门名称",
        ),
        code: str | None = typer.Option(
            None,
            "--code",
            help="部门业务编码（可选）",
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
        parent: str | None = typer.Option(
            None,
            "--parent",
            help="同一机构内的上级部门名称",
        ),
        parent_id: str | None = typer.Option(
            None,
            "--parent-id",
            help="同一机构内的上级部门 ID",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """创建部门.

    --parent 与 --parent-id 只能指定一个，两者均省略时创建根部门。
    上级部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。
    """
    _run(
        "save_department",
        {
            "code": code,
            "name": name,
            "organization": organization,
            "organization_id": organization_id,
            "parent": parent,
            "parent_id": parent_id,
        },
        output,
        required_permission="identity.manage",
    )


@department_app.command("update")
def update_department(
        department: str = typer.Argument(
            ...,
            help="部门名称、完整路径或 ID",
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
        code: str | None = typer.Option(
            None,
            "--code",
            help="部门编码",
        ),
        name: str = typer.Option(
            ...,
            "--name",
            help="部门名称",
        ),
        parent: str | None = typer.Option(
            None,
            "--parent",
            help="同一机构内的上级部门名称",
        ),
        parent_id: str | None = typer.Option(
            None,
            "--parent-id",
            help="同一机构内的上级部门 ID",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """修改部门编码、名称与上级部门.

    --parent 与 --parent-id 只能指定一个，两者均省略时移至根部门。
    上级部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。
    """
    _run(
        "save_department",
        {
            "department_id": department,
            "organization": organization,
            "organization_id": organization_id,
            "code": code,
            "name": name,
            "parent": parent,
            "parent_id": parent_id,
        },
        output,
        required_permission="identity.manage",
    )


@organization_app.command("delete")
def delete_organization(
        organization: str = typer.Argument(..., help="机构名称或 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """删除机构.

    机构仍有关联用户或部门时不能删除，须先调整用户归属并删除所属部门。
    输出：删除前的机构信息。
    """
    _run(
        "delete_organization",
        {"organization_id": organization},
        output,
        required_permission="identity.manage",
    )


@department_app.command("delete")
def delete_department(
        department: str = typer.Argument(..., help="部门名称、完整路径或 ID"),
        organization: str | None = typer.Option(None, "--organization", help="所属机构名称"),
        organization_id: str | None = typer.Option(None, "--organization-id", help="所属机构 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """删除部门.

    按名称或完整路径选择部门时，须指定所属机构；也可直接使用部门 ID。
    部门仍有关联用户或下级部门时不能删除，须先调整用户归属并移动或删除下级部门。
    输出：删除前的部门信息。
    """
    _run(
        "delete_department",
        {"department": department, "organization": organization, "organization_id": organization_id},
        output,
        required_permission="identity.manage",
    )


@organization_app.command("enable")
def enable_organization(
        organization: str = typer.Argument(..., help="机构名称或 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """启用机构.

    停用后保留已有用户归属和历史记录，禁止向该机构及其下级部门新增关联。
    重新启用不会改变下级部门独立设置的启用状态。
    输出：机构信息及启用状态。
    """
    _run(
        "set_organization_active",
        {"organization_id": organization, "is_active": True},
        output,
        required_permission="identity.manage",
    )


@organization_app.command("disable")
def disable_organization(
        organization: str = typer.Argument(..., help="机构名称或 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """停用机构.

    停用后保留已有用户归属和历史记录，禁止向该机构及其下级部门新增关联。
    重新启用不会改变下级部门独立设置的启用状态。
    输出：机构信息及启用状态。
    """
    _run(
        "set_organization_active",
        {"organization_id": organization, "is_active": False},
        output,
        required_permission="identity.manage",
    )


@department_app.command("enable")
def enable_department(
        department: str = typer.Argument(..., help="部门名称、完整路径或 ID"),
        organization: str | None = typer.Option(None, "--organization", help="所属机构名称"),
        organization_id: str | None = typer.Option(None, "--organization-id", help="所属机构 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """启用部门.

    停用后保留已有用户归属和历史记录，禁止向该部门及其下级部门新增关联。
    重新启用不会改变下级部门独立设置的启用状态。
    输出：部门信息及启用状态。
    """
    _run(
        "set_department_active",
        {"department": department, "is_active": True, "organization": organization, "organization_id": organization_id},
        output,
        required_permission="identity.manage",
    )


@department_app.command("disable")
def disable_department(
        department: str = typer.Argument(..., help="部门名称、完整路径或 ID"),
        organization: str | None = typer.Option(None, "--organization", help="所属机构名称"),
        organization_id: str | None = typer.Option(None, "--organization-id", help="所属机构 ID"),
        output: str = typer.Option("text", "--format", help="输出格式：text / json"),
) -> None:
    """停用部门.

    停用后保留已有用户归属和历史记录，禁止向该部门及其下级部门新增关联。
    重新启用不会改变下级部门独立设置的启用状态。
    输出：部门信息及启用状态。
    """
    _run(
        "set_department_active",
        {"department": department, "is_active": False, "organization": organization, "organization_id": organization_id},
        output,
        required_permission="identity.manage",
    )


def _organization_id_from_name(
        catalog: dict[str, list[dict[str, Any]]],
        name: str,
) -> str | None:
    """精确匹配机构名称，存在同名机构时要求使用 ID."""
    if not name:
        return None
    matched = [
        item for item in catalog["organizations"]
        if item["name"] == name
    ]
    if not matched:
        raise ValueError(
            f"机构名称不存在: {name}"
        )
    if len(matched) > 1:
        raise ValueError(
            "存在同名机构，请通过机构 ID 精确指定"
        )
    return matched[0]["organization_id"]


def _department_id_from_name(
        catalog: dict[str, list[dict[str, Any]]],
        organization_id: str | None,
        reference: str,
) -> str | None:
    """按机构匹配部门名称或完整路径，不根据业务编码推断部门."""
    if not reference:
        return None
    path = "/".join(
        part.strip()
        for part in reference.split("/")
    )
    matched = [
        item for item in catalog["departments"]
        if item["organization_id"] == organization_id
        and (
            item["name"] == reference
            or "/".join(node["name"] for node in item.get("path", [])) == path
        )
    ]
    if not matched:
        raise ValueError(
            f"所属机构内不存在部门名称或路径: {reference}"
        )
    if len(matched) > 1:
        raise ValueError(
            "存在同名部门，请使用完整部门路径或部门 ID 精确指定"
        )
    return matched[0]["department_id"]


async def resolve_user_organization(
        *,
        organization: str | None = None,
        department: str | None = None,
        organization_id: str | None = None,
        department_id: str | None = None,
        current_organization_id: str | None = None,
) -> dict[str, str | None]:
    """将机构名称和部门名称或路径解析为内部 ID.

    参数：
        organization: 机构名称，空字符串表示清空
        department: 所属机构内的部门名称或完整路径，空字符串表示清空
        organization_id: 直接指定的机构 ID，不能与机构名称同时提供
        department_id: 直接指定的部门 ID，不能与部门名称同时提供
        current_organization_id: 更新用户时已有的机构 ID

    返回：
        仅包含显式指定字段的机构与部门 ID，未指定字段保留原值

    异常：
        ValueError: 选择方式冲突、名称或路径不存在，或无法唯一确定组织
    """
    if organization is not None and organization_id is not None:
        raise ValueError(
            "--organization 与 --organization-id 不能同时指定"
        )
    if department is not None and department_id is not None:
        raise ValueError(
            "--department 与 --department-id 不能同时指定"
        )

    values: dict[str, Any] = {
        key: value
        for key, value in {
            "organization_id": organization_id,
            "department_id": department_id,
        }.items()
        if value is not None
    }
    if organization is None and department is None:
        return values

    catalog = await OrganizationService().catalog()
    if organization is not None:
        values["organization_id"] = _organization_id_from_name(
            catalog,
            organization.strip(),
        )

    if department is not None:
        name = department.strip()
        selected_organization = values.get(
            "organization_id",
            current_organization_id,
        )
        if name and not selected_organization:
            raise ValueError(
                "指定部门名称前，请先指定或设置所属机构"
            )
        values["department_id"] = _department_id_from_name(
            catalog,
            selected_organization,
            name,
        ) if name else None

    return values
