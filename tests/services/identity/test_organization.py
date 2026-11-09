"""组织目录服务测试.

验证部门路径、机构归属、循环检查及历史身份快照的独立性。

核心功能：
  - test_department_path_preserves_identity_snapshot:
    验证历史路径不随名称变化
  - test_department_parent_rejects_cycles:
    验证禁止自身或下级部门作为上级
  - test_profile_requires_matching_organization:
    验证用户机构与部门一致
  - test_department_parent_rejects_other_organization:
    验证不存在或属于其他机构的上级部门被拒绝
  - test_organization_code_requires_valid_text:
    验证业务编码非空且不超过字段上限
"""

from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.models.departments import Department
from datamind.db.models.organizations import Organization
from datamind.db.models.users import User
from datamind.db.repositories.organization import OrganizationCatalog
from datamind.services.organization import OrganizationService


def create_catalog() -> OrganizationCatalog:
    """创建包含三级部门的组织目录."""
    organization = Organization(
        organization_id="org_hq",
        code="HQ",
        name="总行",
    )
    departments = [
        Department(
            department_id="dpt_hr",
            organization_id="org_hq",
            code="HR",
            name="人力资源部",
        ),
        Department(
            department_id="dpt_recruitment",
            organization_id="org_hq",
            parent_id="dpt_hr",
            code="RECRUITMENT",
            name="招聘组",
        ),
        Department(
            department_id="dpt_campus_recruitment",
            organization_id="org_hq",
            parent_id="dpt_recruitment",
            code="CAMPUS_RECRUITMENT",
            name="校园招聘小组",
        ),
    ]
    return OrganizationCatalog(
        [organization],
        departments,
    )


def test_department_path_preserves_identity_snapshot() -> None:
    """测试名称修改后，已生成的用户身份快照保持原值."""
    catalog = create_catalog()
    user = User(
        user_id="usr_alice",
        username="alice",
        display_name="张三",
        employee_number="001234",
        organization_id="org_hq",
        department_id="dpt_campus_recruitment",
    )

    before = catalog.profile(user)

    assert [item["name"] for item in before["department_path"]] == [
        "人力资源部",
        "招聘组",
        "校园招聘小组",
    ]

    catalog.departments["dpt_recruitment"].name = "人才招聘组"
    user.username = "alice-renamed"

    after = catalog.profile(user)

    assert before["username"] == "alice"
    assert before["employee_number"] == "001234"
    assert before["department_path"][1]["name"] == "招聘组"
    assert after["department_path"][1]["name"] == "人才招聘组"
    assert before["user_id"] == after["user_id"]


@pytest.mark.parametrize(
    "parent_id",
    [
        "dpt_hr",
        "dpt_recruitment",
        "dpt_campus_recruitment",
    ],
)
def test_department_parent_rejects_cycles(
        parent_id: str,
) -> None:
    """测试禁止自身或下级部门作为上级部门."""
    with pytest.raises(
        ValueError,
        match="自身或下级部门",
    ):
        OrganizationService._validate_parent(
            create_catalog(),
            "org_hq",
            parent_id,
            "dpt_hr",
        )


@pytest.mark.parametrize(
    "parent_id",
    [
        "dpt_missing",
        "dpt_branch_hr",
    ],
)
def test_department_parent_rejects_other_organization(
        parent_id: str,
) -> None:
    """测试不存在或属于其他机构的上级部门被拒绝."""
    catalog = create_catalog()
    catalog.organizations["org_branch"] = Organization(
        organization_id="org_branch", code="BRANCH", name="分行",
    )
    catalog.departments["dpt_branch_hr"] = Department(
        department_id="dpt_branch_hr",
        organization_id="org_branch",
        code="HR",
        name="人力资源部",
    )

    with pytest.raises(
        ValueError,
        match="不属于该机构",
    ):
        OrganizationService._validate_parent(
            catalog,
            "org_hq",
            parent_id,
            "dpt_hr",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile, error",
    [
        (
            {
                "organization_id": None,
                "department_id": "dpt_recruitment",
            },
            "必须指定所属机构",
        ),
        (
            {
                "organization_id": "org_hq",
                "department_id": "dpt_branch_hr",
            },
            "不属于所属机构",
        ),
        (
            {
                "organization_id": "org_missing",
                "department_id": None,
            },
            "机构不存在",
        ),
    ],
)
async def test_profile_requires_matching_organization(
        monkeypatch: pytest.MonkeyPatch,
        profile: dict[str, str | None],
        error: str,
) -> None:
    """测试用户的机构和部门存在且相互匹配."""
    repo = SimpleNamespace(
        get_organization=AsyncMock(
            return_value=None
            if profile["organization_id"] == "org_missing"
            else object()
        ),
        get_department=AsyncMock(
            return_value=SimpleNamespace(organization_id="org_branch")
        ),
    )
    monkeypatch.setattr(
        "datamind.services.organization.OrganizationRepository",
        lambda _session: repo,
    )

    with pytest.raises(
        ValueError,
        match=error,
    ):
        await OrganizationService.validate_profile(
            MagicMock(spec=AsyncSession),
            profile,
        )


@pytest.mark.parametrize(
    "value",
    ["", "   ", "a" * 65],
)
def test_organization_code_requires_valid_text(
        value: str,
) -> None:
    """测试业务编码非空且不超过字段上限."""
    with pytest.raises(ValueError):
        OrganizationService._required_text(
            value,
            "机构编码",
            64,
        )
