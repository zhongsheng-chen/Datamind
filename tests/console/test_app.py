# tests/console/test_app.py

"""内网管理控制台应用测试

验证静态页面、浏览器登录 Cookie、会话认证和权限化概览接口。

核心功能：
  - test_console_page_is_available: 验证控制台页面可访问
  - test_session_requires_login: 验证会话接口要求登录
  - test_login_creates_http_only_session: 验证登录创建安全 Cookie
  - test_overview_uses_authenticated_permissions: 验证概览使用用户权限
  - test_section_uses_server_pagination: 验证控制台页面服务端分页
  - test_model_versions_uses_server_pagination: 验证模型版本服务端分页
  - test_experiment_variants_use_server_pagination: 验证实验分组服务端分页
  - test_stream_events_starts_with_consistent_sync: 验证事件流一致性同步
  - test_stream_events_filters_topics_by_permission: 验证事件流权限过滤
"""

import asyncio
import importlib
from collections.abc import (
    AsyncIterator,
    Coroutine,
)
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from datamind.auth.enums import UserStatus
from datamind.auth.schemas import (
    AuthenticatedUser,
    TokenResponse,
)
from datamind.db.models.outbox import OutboxEvent


app_module = importlib.import_module(
    "datamind.console.app"
)


class FakeUnitOfWork:
    """控制台应用测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user() -> AuthenticatedUser:
    """创建控制台测试用户"""
    return AuthenticatedUser(
        user_id="usr_alice",
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        status=UserStatus.ACTIVE,
        roles=["developer"],
        permissions=["model.read"],
    )


@pytest.mark.asyncio
async def test_console_page_is_available() -> None:
    """测试控制台页面和本地静态资源可访问"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get("/")
        stylesheet = await client.get(
            "/assets/style.css"
        )
        script = await client.get(
            "/assets/app.js"
        )
        health = await client.get(
            "/health"
        )

    assert response.status_code == 200
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
    }
    assert "Datamind 管理控制台" in response.text
    assert "让服务的每一次变化，都清晰可见。" in response.text
    assert "登录控制台" in response.text
    assert "Powered by" in response.text
    assert "Zhongsheng Chen" in response.text
    assert "正在建立实时连接" in response.text
    assert "服务状态" in response.text
    assert "API 调用趋势" in response.text
    assert "成功调用" in response.text
    assert "失败调用" in response.text
    assert "返回概览" in response.text
    assert 'label: "模型"' in script.text
    assert 'label: "版本"' in script.text
    assert 'label: "路由"' in script.text
    assert 'label: "实验"' in script.text
    assert 'label: "决策记录"' in script.text
    assert 'title: "最近决策记录"' in script.text
    assert 'title: "部署列表"' in script.text
    assert 'title: "最近部署"' not in script.text
    assert 'title: "实验列表"' in script.text
    assert 'title: "最近实验"' not in script.text
    assert '["model_name", "模型名称"]' in script.text
    assert '["model_version", "模型版本"]' in script.text
    assert '["rollout_type", "发布类型"]' in script.text
    assert '["role", "角色"]' in script.text
    assert '["variant_count", "分组", "action"]' in script.text
    assert 'function renderExperimentVariantsPage(experiment)' in script.text
    assert 'function navigateToExperimentVariants(' in script.text
    assert '["variant_id", "分组 ID", "variant"]' in script.text
    assert 'function showVariantDrawer(record)' in script.text
    assert 'heading.textContent = "实验分组详情"' in script.text
    assert 'appendRequestDetail(summary, "描述", record.description)' in script.text
    assert 'createJsonSection("分组配置", record.config)' in script.text
    assert '["model_id", "模型 ID", "mono"], ["model_version", "模型版本"]' not in script.text
    assert '["version_id", "版本 ID", "mono"], ["environment", "环境"]' not in script.text
    assert '["request_id", "请求 ID", "request"]' in script.text
    assert '["latency_ms", "耗时（毫秒）", "duration"]' in script.text
    assert "createSortHeader" in script.text
    assert "aria-sort" in script.text
    assert 'heading.textContent = "API 调用详情"' in script.text
    assert 'appendRequestDetail(summary, "模型名称", record.model_name)' in script.text
    assert 'appendRequestDetail(summary, "模型版本", record.model_version)' in script.text
    assert 'createSectionNavigationLink(record.deployment_id, "deployments", dialog)' in script.text
    assert 'createSectionNavigationLink(record.decision_id, "decisions", dialog)' in script.text
    assert 'createModelNavigationLink(record, dialog)' in script.text
    assert 'createVersionNavigationLink(record, dialog)' in script.text
    assert 'record.version_id,' in script.text
    assert 'heading.textContent = "决策记录详情"' in script.text
    assert 'createJsonSection("路由上下文", record.context)' in script.text
    assert 'formatJsonValue(value)' in script.text
    assert 'parentField === "feature_scores"' in script.text
    assert ') return value.toFixed(2)' in script.text
    assert 'detail.textContent = hasValue ? value : "—"' in script.text
    assert 'value ?? "—"' in script.text
    assert 'body.append(createRequestError(record.error))' in script.text
    assert 'heading.textContent = "错误信息"' in script.text
    assert 'createJsonSection("请求载荷", record.payload)' in script.text
    assert '"响应结果"' in script.text
    assert "record.response ?? record.prediction" in script.text
    assert ".request-error-section" in stylesheet.text
    assert ".login-credit" in stylesheet.text
    assert 'indicator.textContent = "↕"' not in script.text
    assert 'label: "A/B 实验"' not in script.text
    assert (
        script.text.index('label: "模型"')
        < script.text.index('label: "版本"')
        < script.text.index('label: "部署"')
        < script.text.index('label: "路由"')
        < script.text.index('label: "实验"')
        < script.text.index('label: "运行状态"')
        < script.text.index('label: "API 调用"')
        < script.text.index('label: "决策记录"')
        < script.text.index('label: "审计记录"')
    )
    assert "返回模型" in response.text
    assert "输入关键词查询" in response.text
    assert "frame-ancestors 'none'" in response.headers[
        "content-security-policy"
    ]
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"
    assert stylesheet.status_code == 200
    assert "--navy-950" in stylesheet.text
    assert ".request-drawer-body { display: flex" in stylesheet.text
    assert ".request-detail-grid { display: grid; flex: 0 0 auto" in stylesheet.text
    assert ".request-json-section { flex: 0 0 auto" in stylesheet.text
    assert ".request-json-section pre { margin: 0" in stylesheet.text
    assert ".request-json-section pre { max-height:" not in stylesheet.text


@pytest.mark.asyncio
async def test_session_requires_login() -> None:
    """测试会话接口拒绝未登录请求"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/session"
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "尚未登录"
    }


@pytest.mark.asyncio
async def test_login_creates_http_only_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地账户登录创建 HttpOnly 浏览器会话"""
    service = MagicMock()
    service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=1800,
        )
    )
    service.authenticate_access_token = AsyncMock(
        return_value=create_user()
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "create_auth_service",
        lambda *, session: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_settings",
        lambda: SimpleNamespace(
            auth=SimpleNamespace(
                refresh_token_expires_days=7
            )
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/login",
            json={
                "username": "alice",
                "password": "secret",
            },
        )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert any(
        "datamind_console_access=access-token" in cookie
        and "HttpOnly" in cookie
        and "SameSite=strict" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_refresh=refresh-token" in cookie
        and "HttpOnly" in cookie
        for cookie in cookies
    )


@pytest.mark.asyncio
async def test_overview_uses_authenticated_permissions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台概览按当前用户权限生成"""
    user = create_user()
    service = MagicMock()
    service.snapshot = AsyncMock(
        return_value={
            "access": {
                "models": True
            },
            "sections": {
                "models": []
            },
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/overview"
        )

    assert response.status_code == 200
    service.snapshot.assert_awaited_once_with(
        permissions=["model.read"]
    )


@pytest.mark.asyncio
async def test_model_versions_uses_server_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口使用当前用户权限和分页参数"""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
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
    service.get_access.assert_called_once_with([
        "model.read"
    ])
    service.get_model_versions.assert_awaited_once_with(
        model_id="mdl_test",
        page=2,
        page_size=10,
        query="score",
        sort_by="version",
        sort_order="desc",
    )


@pytest.mark.asyncio
async def test_experiment_variants_use_server_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口使用当前用户权限和分页参数"""
    service = MagicMock()
    service.get_access.return_value = {
        "experiments": True
    }
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
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
    service.get_access.assert_called_once_with([
        "model.read"
    ])
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
    """测试控制台页面接口使用当前用户权限和分页参数"""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/models",
            params={
                "page": 2,
                "page_size": 10,
                "q": "score",
                "sort": "name",
                "order": "asc",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with([
        "model.read"
    ])
    service.get_section.assert_awaited_once_with(
        section="models",
        page=2,
        page_size=10,
        query="score",
        sort_by="name",
        sort_order="asc",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/overview",
        "/api/models/mdl_test/versions",
        "/api/experiments/exp_test/variants",
        "/api/sections/models",
        "/api/events",
    ],
)
async def test_console_data_endpoints_require_login(
        path: str,
) -> None:
    """测试控制台数据接口统一要求登录"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            path
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "尚未登录"
    }


@pytest.mark.asyncio
async def test_overview_reports_unavailable_database(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概览在数据库异常时返回服务不可用"""
    service = MagicMock()
    service.snapshot = AsyncMock(
        side_effect=SQLAlchemyError(
            "database unavailable"
        )
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/overview"
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": "控制台数据暂不可用"
    }


@pytest.mark.asyncio
async def test_model_versions_enforces_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口拒绝无查看权限用户"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": False
    }

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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有模型查看权限"
    }


@pytest.mark.asyncio
async def test_experiment_variants_enforce_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口拒绝无实验查看权限用户"""
    service = MagicMock()
    service.get_access.return_value = {
        "experiments": False
    }

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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/experiments/exp_test/variants"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有实验查看权限"
    }


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
    """测试模型版本接口转换参数和数据库异常"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
    service.get_model_versions = AsyncMock(
        side_effect=error
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("access", "section", "status_code", "message"),
    [
        (
            {
                "models": True
            },
            "unknown",
            404,
            "控制台页面不存在",
        ),
        (
            {
                "models": False
            },
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
    """测试分页接口校验页面存在性和查看权限"""
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/sections/{section}"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


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
    """测试分页接口转换参数和数据库异常"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
    service.get_section = AsyncMock(
        side_effect=error
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
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/models"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


class FakeEventBroker:
    """控制台 SSE 测试事件代理"""

    @asynccontextmanager
    async def subscribe(
            self,
    ) -> AsyncIterator[asyncio.Queue[int]]:
        """返回隔离事件队列"""
        yield asyncio.Queue()


def create_event_request(
        last_event_id: str | None = None,
) -> Request:
    """创建控制台事件流请求"""
    headers: list[tuple[bytes, bytes]] = []

    if last_event_id is not None:
        headers.append((
            b"last-event-id",
            last_event_id.encode(
                "ascii"
            ),
        ))

    async def receive() -> dict[str, object]:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/events",
        "headers": headers,
    }, receive)


@pytest.mark.asyncio
async def test_stream_events_starts_with_consistent_sync(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次连接从最新游标执行一致性同步"""
    async def get_event_window() -> tuple[int | None, int]:
        return None, 12

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    request = create_event_request()
    stream = app_module._stream_events(
        request=request,
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: sync" in message
    assert "id: 12" in message
    assert 'data: {"topics":["models"]}' in message


@pytest.mark.asyncio
async def test_stream_events_filters_topics_by_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流只推送当前用户有权查看的主题"""
    events = [
        OutboxEvent(
            event_id=6,
            topic="models",
            action="update",
        ),
        OutboxEvent(
            event_id=7,
            topic="audits",
            action="insert",
        ),
    ]

    async def get_event_window() -> tuple[int, int]:
        return 1, 7

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return events

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    request = create_event_request(
        "5"
    )
    stream = app_module._stream_events(
        request=request,
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: changed" in message
    assert "id: 7" in message
    assert 'data: {"topics":["models"]}' in message
    assert "audits" not in message


@pytest.mark.asyncio
async def test_events_streams_only_granted_topics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件接口仅建立有权限主题的事件流"""
    user = create_user()
    received_topics: set[str] | None = None

    class DashboardStub:
        """控制台权限测试服务"""

        @staticmethod
        def get_access(
                _permissions: list[str],
        ) -> dict[str, bool]:
            return {
                "models": True,
                "audits": False,
            }

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    async def stream_events(
            *,
            request: Request,
            allowed_topics: set[str],
    ) -> AsyncIterator[str]:
        nonlocal received_topics
        assert request.url.path == "/api/events"
        received_topics = allowed_topics
        yield "event: sync\ndata: {}\n\n"

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        DashboardStub,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_stream_events",
        stream_events,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/events"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == (
        "no-cache, no-transform"
    )
    assert response.headers["x-accel-buffering"] == "no"
    assert received_topics == {
        "models"
    }


async def timeout_wait_for(
        awaitable: Coroutine[object, object, object],
        *,
        timeout: float,
) -> None:
    """关闭等待协程并模拟 SSE 心跳超时"""
    assert timeout > 0
    awaitable.close()
    raise TimeoutError


@pytest.mark.asyncio
async def test_stream_events_reports_expired_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流定期校验并报告登录会话过期"""
    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
            _request: object,
    ) -> None:
        return None

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request(
            "1"
        ),
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: authentication" in message
    assert 'data: {"status":"expired"}' in message


@pytest.mark.asyncio
async def test_stream_events_sends_heartbeat_for_valid_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效会话在空闲时接收 SSE 心跳"""
    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request(
            "1"
        ),
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert message == ": keep-alive\n\n"


@pytest.mark.asyncio
async def test_event_repository_helpers(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件游标范围和增量事件查询"""
    event = OutboxEvent(
        event_id=8,
        topic="models",
        action="update",
    )
    repository = MagicMock()
    repository.get_oldest_event_id = AsyncMock(
        return_value=3
    )
    repository.get_latest_event_id = AsyncMock(
        return_value=8
    )
    repository.list_events = AsyncMock(
        return_value=[
            event
        ]
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "OutboxRepository",
        lambda _session: repository,
    )

    window = await app_module._get_event_window()
    events = await app_module._get_events_after(
        7
    )

    assert window == (
        3,
        8,
    )
    assert events == [
        event
    ]
    repository.list_events.assert_awaited_once_with(
        after_event_id=7,
        limit=200,
    )


def test_event_cursor_and_sse_encoding_helpers() -> None:
    """测试事件游标解析和 SSE 消息编码"""
    assert app_module._parse_event_cursor(None) is None
    assert app_module._parse_event_cursor("invalid") is None
    assert app_module._parse_event_cursor("-1") is None
    assert app_module._parse_event_cursor("0") == 0

    message = app_module._encode_sse(
        event="authentication",
        data={
            "status": "expired"
        },
    )

    assert message == (
        "event: authentication\n"
        'data: {"status":"expired"}\n\n'
    )


def test_client_ip_returns_none_without_client() -> None:
    """测试缺少客户端地址时返回 None"""
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    })

    assert app_module._client_ip(request) is None


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_event_broker(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应用生命周期管理事件代理"""
    broker = MagicMock()
    broker.start = AsyncMock()
    broker.stop = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        broker,
    )

    async with app_module._lifespan(
            app_module.console_app
    ):
        broker.start.assert_awaited_once_with()
        broker.stop.assert_not_awaited()

    broker.stop.assert_awaited_once_with()
