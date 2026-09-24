"""Console sections HTTP contract tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from datamind.auth.schemas import AuthenticatedUser
from tests.console._app_support import app_module, create_user


@pytest.mark.asyncio
async def test_management_options_return_selectable_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试管理表单返回模型类型、权限和有效角色选项."""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
                "identity.manage",
            ]
        }
    )
    identity_service = MagicMock()
    identity_service.list_roles = AsyncMock(
        return_value=[
            {
                "name": "developer",
                "description": "开发人员",
            }
        ]
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "IdentityService",
        lambda: identity_service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/management/options")

    assert response.status_code == 200
    payload = response.json()
    assert "logistic_regression" in payload["model_types"]
    assert payload["artifact_extensions"] == {
        "sklearn": [".pkl", ".pickle", ".joblib"],
        "xgboost": [".json", ".ubj", ".model"],
        "lightgbm": [".txt", ".model"],
        "catboost": [".cbm"],
    }
    routing_rules = payload["routing_rules"]
    assert routing_rules["example"] == {
        "match": "all",
        "conditions": [
            {
                "field": "features.credit_utilization_ratio",
                "op": "gte",
                "value": 0.7,
            },
        ],
    }
    assert routing_rules["schema"]["type"] == "object"
    assert routing_rules["schema"]["examples"] == [routing_rules["example"]]
    assert payload["permissions"][0] == "*"
    assert "model.read" in payload["permissions"]
    assert payload["roles"] == [
        {
            "name": "developer",
            "description": "开发人员",
        }
    ]
    identity_service.list_roles.assert_awaited_once_with(
        status=app_module.RoleStatus.ACTIVE,
        limit=1000,
    )


@pytest.mark.asyncio
async def test_overview_uses_authenticated_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台概览按当前用户权限生成."""
    user = create_user()
    service = MagicMock()
    service.snapshot = AsyncMock(
        return_value={
            "access": {"models": True},
            "sections": {"models": []},
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/overview")

    assert response.status_code == 200
    service.snapshot.assert_awaited_once_with(
        permissions=["model.read"],
        trend_range="24h",
    )


@pytest.mark.asyncio
async def test_overview_uses_requested_trend_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概览传递 API 调用趋势时间范围."""
    service = MagicMock()
    service.snapshot = AsyncMock(
        return_value={
            "access": {},
            "sections": {},
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/overview?range=7d")

    assert response.status_code == 200
    service.snapshot.assert_awaited_once_with(
        permissions=["model.read"],
        trend_range="7d",
    )


@pytest.mark.asyncio
async def test_model_versions_uses_server_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口使用当前用户权限和分页参数."""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {"models": True}
    service.get_model_versions = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions",
            params={
                "page": 2,
                "page_size": 10,
                "q": "score",
                "sort": "version",
                "order": "desc",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with(["model.read"])
    service.get_model_versions.assert_awaited_once_with(
        model_id="mdl_test",
        page=2,
        page_size=10,
        query="score",
        sort_by="version",
        sort_order="desc",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_experiment_variants_use_server_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口使用当前用户权限和分页参数."""
    service = MagicMock()
    service.get_access.return_value = {"experiments": True}
    service.get_experiment_variants = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/experiments/exp_test/variants",
            params={
                "page": 2,
                "page_size": 10,
                "q": "control",
                "sort": "weight",
                "order": "desc",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with(["model.read"])
    service.get_experiment_variants.assert_awaited_once_with(
        experiment_id="exp_test",
        page=2,
        page_size=10,
        query="control",
        sort_by="weight",
        sort_order="desc",
    )


@pytest.mark.asyncio
async def test_section_uses_server_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台页面接口使用当前用户权限和分页参数."""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {"versions": True}
    service.get_section = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/versions",
            params={
                "page": 2,
                "page_size": 10,
                "q": "score",
                "sort": "name",
                "order": "asc",
                "deleted": "true",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with(["model.read"])
    service.get_section.assert_awaited_once_with(
        section="versions",
        page=2,
        page_size=10,
        query="score",
        sort_by="name",
        sort_order="asc",
        deleted=True,
    )


@pytest.mark.asyncio
async def test_runtime_section_uses_current_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行实例接口只查询当前实例."""
    service = MagicMock()
    service.get_access.return_value = {"runtimes": True}
    service.get_section = AsyncMock(
        return_value={
            "items": [],
            "page": 1,
            "page_size": 10,
            "has_previous": False,
            "has_next": False,
        }
    )

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/runtimes",
        )

    assert response.status_code == 200
    service.get_section.assert_awaited_once_with(
        section="runtimes",
        page=1,
        page_size=10,
        query="",
        sort_by=None,
        sort_order="asc",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_overview_reports_unavailable_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概览在数据库异常时返回服务不可用."""
    service = MagicMock()
    service.snapshot = AsyncMock(side_effect=SQLAlchemyError("database unavailable"))

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/overview")

    assert response.status_code == 503
    assert response.json() == {"error": "控制台数据暂不可用"}


@pytest.mark.asyncio
async def test_model_versions_enforces_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口拒绝无查看权限用户."""
    service = MagicMock()
    service.get_access.return_value = {"models": False}

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/models/mdl_test/versions")

    assert response.status_code == 403
    assert response.json() == {"error": "没有模型查看权限"}


@pytest.mark.asyncio
async def test_experiment_variants_enforce_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口拒绝无实验查看权限用户."""
    service = MagicMock()
    service.get_access.return_value = {"experiments": False}

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/experiments/exp_test/variants")

    assert response.status_code == 403
    assert response.json() == {"error": "没有实验查看权限"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "message"),
    [
        (
            ValueError("分页参数无效"),
            400,
            "分页参数无效",
        ),
        (
            SQLAlchemyError("database unavailable"),
            503,
            "模型版本数据暂不可用",
        ),
    ],
)
async def test_model_versions_maps_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    message: str,
) -> None:
    """测试模型版本接口转换参数和数据库异常."""
    service = MagicMock()
    service.get_access.return_value = {"models": True}
    service.get_model_versions = AsyncMock(side_effect=error)

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/models/mdl_test/versions")

    assert response.status_code == status_code
    assert response.json() == {"error": message}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("access", "section", "status_code", "message"),
    [
        (
            {"models": True},
            "unknown",
            404,
            "控制台页面不存在",
        ),
        (
            {"models": False},
            "models",
            403,
            "没有页面查看权限",
        ),
    ],
)
async def test_section_validates_access(
    monkeypatch: pytest.MonkeyPatch,
    access: dict[str, bool],
    section: str,
    status_code: int,
    message: str,
) -> None:
    """测试分页接口校验页面存在性和查看权限."""
    service = MagicMock()
    service.get_access.return_value = access

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/api/sections/{section}")

    assert response.status_code == status_code
    assert response.json() == {"error": message}


@pytest.mark.asyncio
async def test_section_rejects_identity_reader_for_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份只读用户不能访问控制台用户列表."""
    user = create_user().model_copy(update={"permissions": ["identity.read"]})

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/sections/users")

    assert response.status_code == 403
    assert response.json() == {"error": "没有页面查看权限"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "message"),
    [
        (
            ValueError("分页参数无效"),
            400,
            "分页参数无效",
        ),
        (
            SQLAlchemyError("database unavailable"),
            503,
            "控制台页面数据暂不可用",
        ),
    ],
)
async def test_section_maps_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    message: str,
) -> None:
    """测试分页接口转换参数和数据库异常."""
    service = MagicMock()
    service.get_access.return_value = {"models": True}
    service.get_section = AsyncMock(side_effect=error)

    async def authenticate(
        _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/sections/models")

    assert response.status_code == status_code
    assert response.json() == {"error": message}
