"""组织管理命令测试.

验证机构、部门命令及用户组织资料命令使用已认证操作人并传递正确参数。

核心功能：
  - test_directory_commands_use_identity_permission:
    验证组织维护需要身份管理权限
  - test_update_user_only_passes_selected_profile:
    验证部分更新保留未指定资料
  - test_create_user_passes_employee_and_organization:
    验证工号和组织归属传递
  - test_user_organization_names_resolve_within_organization:
    验证完整部门路径按所属机构解析，支持沿用机构及显式清空
  - test_user_organization_rejects_name_and_id_together:
    验证同一组织字段不能同时使用名称和内部 ID
  - test_department_commands_resolve_names:
    验证机构、上级部门和修改目标按名称或路径解析为内部 ID
  - test_department_rejects_ambiguous_or_missing_organization:
    验证机构必填且同一资源不能同时使用名称和 ID
  - test_department_path_disambiguates_duplicate_names:
    验证不同分支的同名部门通过完整路径精确选择
  - test_department_selection_does_not_match_business_code:
    验证日常名称选择不会被同名业务编码误导
  - test_duplicate_organization_names_require_explicit_id:
    验证同名机构不会自动匹配第一条记录
  - test_delete_commands_resolve_targets:
    验证删除命令按名称、完整路径或 ID 选择资源并校验身份管理权限
  - test_delete_department_requires_organization_for_name:
    验证缺少机构时拒绝按名称删除部门
  - test_activation_commands_use_identity_permission:
    验证机构与部门启停命令传递布尔状态并校验身份管理权限
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from typer.testing import CliRunner

import datamind.cli.organization as organization_module
from datamind.cli.main import app
from tests.cli.test_identity import FakeCLIContext


runner = CliRunner()


def department_record(
        department_id: str,
        name: str,
        code: str | None,
        *,
        organization_id: str = "org_hq",
        parent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造完整部门示例，子节点继承父节点路径并保持同机构归属."""
    if parent is not None:
        assert parent["organization_id"] == organization_id
    node = {"department_id": department_id, "name": name, "code": code}
    return {
        **node,
        "organization_id": organization_id,
        "parent_id": parent["department_id"] if parent is not None else None,
        "path": [*(parent["path"] if parent is not None else []), node.copy()],
        "is_active": True,
        "is_available": True,
    }


@pytest.fixture
def organization_directory() -> dict[str, list[dict[str, Any]]]:
    """总行和分行均设人力资源部，招聘组直接隶属于各自的人力资源部."""
    hr = department_record("dpt_hr", "人力资源部", "HR")
    branch_hr = department_record(
        "dpt_branch_hr",
        "人力资源部",
        "HR",
        organization_id="org_branch",
    )
    return {
        "organizations": [
            {
                "organization_id": "org_hq",
                "name": "总行",
                "code": "HQ",
                "is_active": True,
            },
            {
                "organization_id": "org_branch",
                "name": "分行",
                "code": "BRANCH",
                "is_active": True,
            },
        ],
        "departments": [
            hr,
            department_record("dpt_recruitment", "招聘组", "RECRUITMENT", parent=hr),
            branch_hr,
            department_record(
                "dpt_branch_recruitment",
                "招聘组",
                "RECRUITMENT",
                organization_id="org_branch",
                parent=branch_hr,
            ),
        ],
    }


@pytest.mark.parametrize(
    "arguments, method, expected",
    [
        pytest.param(
            ["organization", "create", "总行"],
            "save_organization",
            {"name": "总行"},
            id="create-organization-without-code",
        ),
        pytest.param(
            ["organization", "create", "总行", "--code", "HQ"],
            "save_organization",
            {"name": "总行", "code": "HQ"},
            id="create-organization-with-code",
        ),
        pytest.param(
            [
                "department", "create", "招聘组",
                "--code", "RECRUITMENT",
                "--organization-id", "org_hq",
                "--parent-id", "dpt_hr",
            ],
            "save_department",
            {
                "name": "招聘组",
                "code": "RECRUITMENT",
                "organization_id": "org_hq",
                "parent_id": "dpt_hr",
            },
            id="create-child-department-by-id",
        ),
    ],
)
def test_directory_commands_use_identity_permission(
        monkeypatch: pytest.MonkeyPatch,
        arguments: list[str],
        method: str,
        expected: dict[str, str],
) -> None:
    """验证组织命令要求身份管理权限，并正确传递所属机构和上级部门."""
    service = MagicMock()
    record: dict[str, Any] = {
        "organization_id": "org_hq",
        "name": expected["name"],
        "code": expected.get("code"),
        "is_active": True,
    }
    if method == "save_department":
        hr = department_record("dpt_hr", "人力资源部", "HR")
        record = department_record(
            "dpt_recruitment",
            "招聘组",
            "RECRUITMENT",
            parent=hr,
        )
    operation = AsyncMock(return_value=record)
    setattr(
        service,
        method,
        operation,
    )
    context = MagicMock(return_value=FakeCLIContext())
    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        context,
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [*arguments, "--format", "json"],
    )

    assert result.exit_code == 0, result.output

    context.assert_called_once_with(required_permission="identity.manage")
    operation.assert_awaited_once_with(**expected)
    assert json.loads(result.output) == record


def test_update_user_only_passes_selected_profile(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证仅修改工号时，不覆盖机构、部门、用户名和显示名称."""
    service = SimpleNamespace(
        get_user=AsyncMock(
            return_value={
                "username": "alice",
                "display_name": "张三",
                "email": "alice@example.com",
                "employee_number": "009999",
                "organization_id": "org_hq",
                "department_id": "dpt_hr",
            }
        ),
        update_user=AsyncMock(return_value={"user_id": "usr_alice"}),
    )
    monkeypatch.setattr(
        "datamind.cli.user.update.cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )
    monkeypatch.setattr(
        "datamind.cli.user.update.IdentityService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        ["user", "update", "alice", "--employee-number", "001234", "--format", "json"],
    )

    assert result.exit_code == 0, result.output

    arguments = service.update_user.call_args.kwargs

    assert arguments["organization_profile"] == {"employee_number": "001234"}
    assert arguments["new_username"] == "alice"
    assert arguments["display_name"] == "张三"
    assert arguments["email"] == "alice@example.com"
    assert arguments["operator_id"] == "usr_admin"


def test_create_user_passes_employee_and_organization(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证工号前导零、所属机构和部门通过 CLI 传递给身份服务."""
    service = SimpleNamespace(
        create_user=AsyncMock(return_value={"user_id": "usr_alice"}),
    )
    monkeypatch.setattr(
        "datamind.cli.user.create.cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )
    monkeypatch.setattr(
        "datamind.cli.user.create.IdentityService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [
            "user", "create", "alice",
            "--employee-number", "001234",
            "--organization-id", "org_hq",
            "--department-id", "dpt_hr",
            "--format", "json",
        ],
        input="secret-password\nsecret-password\n",
    )

    assert result.exit_code == 0, result.output

    arguments = service.create_user.call_args.kwargs

    assert arguments["employee_number"] == "001234"
    assert arguments["organization_id"] == "org_hq"
    assert arguments["department_id"] == "dpt_hr"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments, expected",
    [
        (
            {
                "organization": "总行",
                "department": "人力资源部/招聘组",
            },
            {
                "organization_id": "org_hq",
                "department_id": "dpt_recruitment",
            },
        ),
        (
            {
                "department": "人力资源部/招聘组",
                "current_organization_id": "org_hq",
            },
            {"department_id": "dpt_recruitment"},
        ),
        (
            {
                "organization": "",
                "department": "",
            },
            {
                "organization_id": None,
                "department_id": None,
            },
        ),
    ],
)
async def test_user_organization_names_resolve_within_organization(
        monkeypatch: pytest.MonkeyPatch,
        organization_directory: dict[str, list[dict[str, Any]]],
        arguments: dict,
        expected: dict,
) -> None:
    """验证完整部门路径按所属机构解析，支持沿用机构及显式清空."""
    service = SimpleNamespace(catalog=AsyncMock(return_value=organization_directory))
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    actual = await organization_module.resolve_user_organization(**arguments)

    assert actual == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {
            "organization": "总行",
            "organization_id": "org_hq",
        },
        {
            "department": "人力资源部/招聘组",
            "department_id": "dpt_recruitment",
        },
    ],
)
async def test_user_organization_rejects_name_and_id_together(
        arguments: dict,
) -> None:
    """验证同一组织字段不能同时使用名称和内部 ID."""
    with pytest.raises(
        ValueError,
        match="不能同时指定",
    ):
        await organization_module.resolve_user_organization(**arguments)


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (
            ["department", "create", "审计部", "--organization", "总行"],
            {
                "name": "审计部",
                "organization_id": "org_hq",
                "parent_id": None,
            },
        ),
        (
            ["department", "create", "财务部", "--code", "FINANCE", "--organization", "总行"],
            {
                "code": "FINANCE",
                "name": "财务部",
                "organization_id": "org_hq",
                "parent_id": None,
            },
        ),
        (
            [
                "department", "create", "招聘组",
                "--code", "RECRUITMENT",
                "--organization", "总行",
                "--parent", "人力资源部",
            ],
            {
                "code": "RECRUITMENT",
                "name": "招聘组",
                "organization_id": "org_hq",
                "parent_id": "dpt_hr",
            },
        ),
        (
            [
                "department", "update", "dpt_recruitment",
                "--organization", "总行",
                "--parent", "人力资源部",
                "--code", "RECRUITMENT",
                "--name", "招聘组",
            ],
            {
                "department_id": "dpt_recruitment",
                "code": "RECRUITMENT",
                "name": "招聘组",
                "organization_id": "org_hq",
                "parent_id": "dpt_hr",
            },
        ),
        (
            [
                "department", "update", "招聘组",
                "--organization", "总行",
                "--parent", "人力资源部",
                "--code", "RECRUITMENT",
                "--name", "招聘组",
            ],
            {
                "department_id": "dpt_recruitment",
                "code": "RECRUITMENT",
                "name": "招聘组",
                "organization_id": "org_hq",
                "parent_id": "dpt_hr",
            },
        ),
        (
            [
                "department", "update", "人力资源部/招聘组",
                "--organization", "总行",
                "--parent", "人力资源部",
                "--code", "RECRUITMENT",
                "--name", "招聘组",
            ],
            {
                "department_id": "dpt_recruitment",
                "code": "RECRUITMENT",
                "name": "招聘组",
                "organization_id": "org_hq",
                "parent_id": "dpt_hr",
            },
        ),
    ],
)
def test_department_commands_resolve_names(
        monkeypatch: pytest.MonkeyPatch,
        organization_directory: dict[str, list[dict[str, Any]]],
        arguments: list[str],
        expected: dict[str, str | None],
) -> None:
    """验证机构、上级部门和修改目标按名称或路径解析为内部 ID."""
    catalog = organization_directory
    name = expected["name"]
    assert name is not None
    department_ids = {
        "审计部": "dpt_audit",
        "财务部": "dpt_finance",
        "招聘组": "dpt_recruitment",
    }
    identifier = department_ids[name]
    if arguments[1] == "create":
        catalog["departments"] = [
            item
            for item in catalog["departments"]
            if item["department_id"] != identifier
        ]
    hr = next(
        item for item in catalog["departments"] if item["department_id"] == "dpt_hr"
    )
    record = department_record(
        identifier,
        name,
        expected.get("code"),
        parent=hr if expected["parent_id"] else None,
    )
    service = SimpleNamespace(
        catalog=AsyncMock(return_value=catalog),
        save_department=AsyncMock(return_value=record),
    )
    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [
            *arguments,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output

    service.save_department.assert_awaited_once_with(**expected)
    assert json.loads(result.output) == record


@pytest.mark.parametrize(
    "selectors, error",
    [
        (
            ["--organization", "总行", "--organization-id", "org_hq"],
            "不能同时指定",
        ),
        (
            ["--organization-id", "org_hq", "--parent", "人力资源部", "--parent-id", "dpt_hr"],
            "不能同时指定",
        ),
        (
            [],
            "请指定 --organization 或 --organization-id",
        ),
    ],
)
def test_department_rejects_ambiguous_or_missing_organization(
        monkeypatch: pytest.MonkeyPatch,
        selectors: list[str],
        error: str,
) -> None:
    """验证机构必填且同一资源不能同时使用名称和 ID."""
    service = SimpleNamespace(save_department=AsyncMock())
    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [
            "department",
            "create",
            "人力资源部",
            "--code",
            "HR",
            *selectors,
        ],
    )

    assert result.exit_code == 1
    assert error in result.output

    service.save_department.assert_not_awaited()


@pytest.mark.parametrize(
    "reference, expected",
    [
        (
            "个人金融部/运营组",
            "dpt_retail_operations",
        ),
        (
            "公司金融部 / 运营组",
            "dpt_corporate_operations",
        ),
    ],
)
def test_department_path_disambiguates_duplicate_names(
        reference: str,
        expected: str,
) -> None:
    """验证不同分支的同名部门通过完整路径精确选择."""
    retail = department_record("dpt_retail", "个人金融部", "RETAIL")
    corporate = department_record("dpt_corporate", "公司金融部", "CORPORATE")
    catalog: dict[str, list[dict[str, Any]]] = {
        "organizations": [
            {
                "organization_id": "org_hq",
                "name": "总行",
                "code": "HQ",
                "is_active": True,
            }
        ],
        "departments": [
            retail,
            department_record("dpt_retail_operations", "运营组", None, parent=retail),
            corporate,
            department_record(
                "dpt_corporate_operations",
                "运营组",
                None,
                parent=corporate,
            ),
        ],
    }

    result = organization_module._department_id_from_name(
        catalog,
        "org_hq",
        reference,
    )

    assert result == expected

    with pytest.raises(
        ValueError,
        match="同名部门",
    ):
        organization_module._department_id_from_name(
            catalog,
            "org_hq",
            "运营组",
        )


def test_department_selection_does_not_match_business_code() -> None:
    """验证日常名称选择不会被同名业务编码误导."""
    # HR 既是第一个部门的编码，也是另一个部门的合法名称，刻意构造冲突边界。
    catalog: dict[str, list[dict[str, Any]]] = {
        "organizations": [
            {
                "organization_id": "org_hq",
                "name": "总行",
                "code": "HQ",
                "is_active": True,
            }
        ],
        "departments": [
            department_record("dpt_hr", "人力资源部", "HR"),
            department_record("dpt_named_hr", "HR", None),
        ],
    }

    assert (
        organization_module._department_id_from_name(
            catalog,
            "org_hq",
            "HR",
        )
        == "dpt_named_hr"
    )


def test_duplicate_organization_names_require_explicit_id() -> None:
    """验证同名机构不会自动匹配第一条记录."""
    catalog: dict[str, list[dict[str, Any]]] = {
        "organizations": [
            {
                "organization_id": "org_first",
                "code": "FIRST",
                "name": "总行",
            },
            {
                "organization_id": "org_second",
                "code": "SECOND",
                "name": "总行",
            },
        ],
        "departments": [],
    }
    with pytest.raises(
        ValueError,
        match="同名机构",
    ):
        organization_module._organization_id_from_name(
            catalog,
            "总行",
        )


@pytest.mark.parametrize(
    "arguments, method, expected",
    [
        (
            ["organization", "delete", "总行"],
            "delete_organization",
            {"organization_id": "org_hq"},
        ),
        (
            ["organization", "delete", "org_hq"],
            "delete_organization",
            {"organization_id": "org_hq"},
        ),
        (
            ["department", "delete", "人力资源部/招聘组", "--organization", "总行"],
            "delete_department",
            {"department_id": "dpt_recruitment"},
        ),
        (
            ["department", "delete", "dpt_recruitment"],
            "delete_department",
            {"department_id": "dpt_recruitment"},
        ),
    ],
)
def test_delete_commands_resolve_targets(
        monkeypatch: pytest.MonkeyPatch,
        organization_directory: dict[str, list[dict[str, Any]]],
        arguments: list[str],
        method: str,
        expected: dict[str, str],
) -> None:
    """测试删除命令按名称、完整路径或 ID 选择资源并校验身份管理权限."""
    catalog = organization_directory

    if method == "delete_organization":
        catalog["departments"] = [
            item
            for item in catalog["departments"]
            if item["organization_id"] != "org_hq"
        ]

        record = next(
            item
            for item in catalog["organizations"]
            if item["organization_id"] == "org_hq"
        )
    else:
        record = next(
            item
            for item in catalog["departments"]
            if item["department_id"] == "dpt_recruitment"
        )

    operation = AsyncMock(return_value=record)
    service = SimpleNamespace(
        catalog=AsyncMock(return_value=catalog),
    )
    setattr(
        service,
        method,
        operation,
    )

    context = MagicMock(return_value=FakeCLIContext())
    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        context,
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [*arguments, "--format", "json"],
    )

    assert result.exit_code == 0, result.output

    operation.assert_awaited_once_with(**expected)
    assert json.loads(result.output) == record
    context.assert_called_once_with(required_permission="identity.manage")


def test_delete_department_requires_organization_for_name(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试缺少机构时拒绝按名称删除部门."""
    operation = AsyncMock()

    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: SimpleNamespace(delete_department=operation),
    )

    result = runner.invoke(
        app,
        ["department", "delete", "招聘组"],
    )

    assert result.exit_code == 1
    assert "所属机构" in result.output

    operation.assert_not_awaited()


@pytest.mark.parametrize(
    "resource, reference, key",
    [
        ("organization", "org_hq", "organization_id"),
        ("department", "dpt_recruitment", "department_id"),
    ],
)
@pytest.mark.parametrize("action", ["enable", "disable"])
def test_activation_commands_use_identity_permission(
        monkeypatch: pytest.MonkeyPatch,
        organization_directory: dict[str, list[dict[str, Any]]],
        resource: str,
        reference: str,
        key: str,
        action: str,
) -> None:
    """测试机构与部门启停命令传递布尔状态并校验身份管理权限."""
    records = organization_directory[
        "organizations" if resource == "organization" else "departments"
    ]
    record = next(
        item.copy()
        for item in records
        if item[key] == reference
    )
    record["is_active"] = action == "enable"

    if resource == "department":
        record["is_available"] = action == "enable"

    operation = AsyncMock(return_value=record)
    service = SimpleNamespace(
        **{f"set_{resource}_active": operation},
    )

    context = MagicMock(return_value=FakeCLIContext())
    monkeypatch.setattr(
        "datamind.cli.organization.cli_context",
        context,
    )
    monkeypatch.setattr(
        "datamind.cli.organization.OrganizationService",
        lambda: service,
    )

    result = runner.invoke(
        app,
        [resource, action, reference, "--format", "json"],
    )

    assert result.exit_code == 0, result.output

    operation.assert_awaited_once_with(
        **{key: reference, "is_active": action == "enable"},
    )
    assert json.loads(result.output) == record
    context.assert_called_once_with(required_permission="identity.manage")
