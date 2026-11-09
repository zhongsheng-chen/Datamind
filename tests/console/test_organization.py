"""组织目录接口测试.

验证目录查询权限、写操作 CSRF 保护和请求字段校验。

核心功能：
  - test_directory_read_does_not_require_csrf:
    验证目录查询为只读操作
  - test_directory_requires_identity_permission:
    验证组织资料仅向身份管理员开放
  - test_directory_write_requires_csrf:
    验证写操作保留 CSRF 防护
  - test_user_update_preserves_explicit_profile_fields:
    验证组织资料的设置与清空
  - test_directory_delete_authorization_and_conflicts:
    验证删除接口无需请求体，校验权限和 CSRF，并将关联冲突映射为 409
  - test_directory_activation_authorization:
    验证组织启停接口无需请求体，并校验身份管理权限和 CSRF
  - test_directory_reorder_authorization:
    验证机构与部门排序保留权限与 CSRF 校验
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)

from tests.console._app_support import (
    app_module,
    create_user,
)


@pytest.mark.asyncio
async def test_directory_read_does_not_require_csrf(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已授权用户可直接读取目录，无需写操作的 CSRF 令牌."""
    user = create_user().model_copy(
        update={"permissions": ["identity.manage"]},
    )
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )

    catalog = AsyncMock(
        return_value={
            "organizations": [],
            "departments": [],
        },
    )
    monkeypatch.setattr(
        "datamind.console.app.OrganizationService.catalog",
        catalog,
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        response = await client.get("/api/directory")

    assert response.status_code == 200

    catalog.assert_awaited_once()


@pytest.mark.asyncio
async def test_directory_requires_identity_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试普通模型使用者不能读取或修改组织目录."""
    user = create_user().model_copy(
        update={"permissions": ["model.read"]},
    )
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        for method, path in [
            (
                "GET",
                "/api/directory",
            ),
            (
                "POST",
                "/api/organizations",
            ),
        ]:
            response = await client.request(
                method,
                path,
            )

            assert response.status_code == 403


@pytest.mark.asyncio
async def test_directory_write_requires_csrf(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份管理员的写操作仍需有效 CSRF 令牌."""
    user = create_user().model_copy(
        update={"permissions": ["identity.manage"]},
    )
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/organizations",
            json={
                "code": "HQ",
                "name": "总行",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    [
        {
            "employee_number": "001234",
            "organization_id": "org_hq",
            "department_id": "dpt_hr",
        },
        {
            "organization_id": None,
            "department_id": None,
        },
    ],
)
async def test_user_update_preserves_explicit_profile_fields(
        monkeypatch: pytest.MonkeyPatch,
        profile: dict[str, str | None],
) -> None:
    """测试 PATCH 将显式设置或清空的组织字段传递给身份服务."""
    user = create_user().model_copy(
        update={"permissions": ["identity.manage"]},
    )
    service = SimpleNamespace(
        update_user=AsyncMock(return_value={"user_id": "usr_alice"}),
    )
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(
        "datamind.console.app._identity_service_for_request",
        lambda *_args, **_kwargs: service,
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-test",
        )

        response = await client.patch(
            "/api/users/alice",
            json={
                "username": "alice",
                **profile,
            },
            headers={
                "X-CSRF-Token": "csrf-test",
                "Origin": "http://testserver",
            },
        )

    assert response.status_code == 200
    assert service.update_user.call_args.kwargs["organization_profile"] == profile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource, key",
    [
        ("organizations", "organization_id"),
        ("departments", "department_id"),
    ],
)
@pytest.mark.parametrize("access", ["allowed", "permission", "csrf", "conflict"])
async def test_directory_delete_authorization_and_conflicts(
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        key: str,
        access: str,
) -> None:
    """测试删除接口无需请求体，校验权限和 CSRF，并将关联冲突映射为 409."""
    from datamind.services.errors import IdentityConflictError

    permissions = ["model.read"] if access == "permission" else ["identity.manage"]
    user = create_user().model_copy(
        update={"permissions": permissions},
    )

    operation = AsyncMock(return_value={key: "test-id", "name": "待删除"})

    if access == "conflict":
        operation.side_effect = IdentityConflictError("仍有关联用户")

    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )
    target = (
        "datamind.console.app.OrganizationService.delete_organization"
        if resource == "organizations"
        else "datamind.console.app.OrganizationService.delete_department"
    )
    monkeypatch.setattr(target, operation)

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-test",
        )

        headers = (
            {}
            if access == "csrf"
            else {
                "X-CSRF-Token": "csrf-test",
                "Origin": "http://testserver",
            }
        )

        response = await client.delete(
            f"/api/{resource}/test-id",
            headers=headers,
        )

    assert response.status_code == {
        "allowed": 200,
        "permission": 403,
        "csrf": 403,
        "conflict": 409,
    }[access]

    if access in ("allowed", "conflict"):
        operation.assert_awaited_once_with(**{key: "test-id"})
    else:
        operation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource, key",
    [
        ("organizations", "organization_id"),
        ("departments", "department_id"),
    ],
)
@pytest.mark.parametrize("action", ["enable", "disable"])
@pytest.mark.parametrize("access", ["allowed", "permission", "csrf"])
async def test_directory_activation_authorization(
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        key: str,
        action: str,
        access: str,
) -> None:
    """测试组织启停接口无需请求体，并校验身份管理权限和 CSRF."""
    user = create_user().model_copy(
        update={
            "permissions": (
                ["model.read"]
                if access == "permission"
                else ["identity.manage"]
            ),
        },
    )
    operation = AsyncMock(
        return_value={key: "test-id", "is_active": action == "enable"},
    )
    target = (
        "datamind.console.app.OrganizationService.set_organization_active"
        if resource == "organizations"
        else "datamind.console.app.OrganizationService.set_department_active"
    )
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(target, operation)

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-test",
        )

        headers = (
            {}
            if access == "csrf"
            else {
                "X-CSRF-Token": "csrf-test",
                "Origin": "http://testserver",
            }
        )

        response = await client.post(
            f"/api/{resource}/test-id/{action}",
            headers=headers,
        )

    assert response.status_code == (200 if access == "allowed" else 403)

    if access == "allowed":
        operation.assert_awaited_once_with(
            **{key: "test-id", "is_active": action == "enable"},
        )
    else:
        operation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource, key",
    [
        ("organizations", "organization_id"),
        ("departments", "department_id"),
    ],
)
@pytest.mark.parametrize("action", ["move"])
@pytest.mark.parametrize("access", ["allowed", "permission", "csrf"])
async def test_directory_reorder_authorization(
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        key: str,
        action: str,
        access: str,
) -> None:
    """测试机构与部门排序校验身份管理权限和 CSRF."""
    user = create_user().model_copy(
        update={
            "permissions": (
                ["model.read"]
                if access == "permission"
                else ["identity.manage"]
            ),
        },
    )
    operation = AsyncMock(return_value={key: "test-id", "sort_order": 2})
    target = "datamind.console.app.OrganizationService.move"
    monkeypatch.setattr(
        "datamind.console.app._authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(target, operation)

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-test",
        )

        headers = (
            {}
            if access == "csrf"
            else {
                "X-CSRF-Token": "csrf-test",
                "Origin": "http://testserver",
            }
        )

        response = await client.post(
            f"/api/{resource}/test-id/{action}",
            headers=headers,
            json={"direction": "down"},
        )

    assert response.status_code == (200 if access == "allowed" else 403)

    if access == "allowed":
        operation.assert_awaited_once_with(
            resource="organization" if resource == "organizations" else "department",
            target_id="test-id",
            direction="down",
        )
    else:
        operation.assert_not_awaited()
