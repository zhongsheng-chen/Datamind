"""运行时服务安全边界测试.

验证环境保护、Bearer 令牌解析、权限校验和可信请求上下文。

核心功能：
  - test_production_rejects_disabled_auth:
    验证生产环境拒绝关闭认证
  - test_testing_allows_local_anonymous_identity:
    验证测试环境允许本地匿名身份
  - test_extract_bearer_token_normalizes_valid_header:
    验证解析并规范化 Bearer 令牌
  - test_authenticate_validates_required_permission:
    验证认证过程校验所需权限
  - test_request_scope_establishes_trusted_context:
    验证请求作用域建立可信上下文
  - test_security_documentation_lists_public_components:
    验证核心功能列出安全模块公共组件
  - test_extract_bearer_token_rejects_invalid_header:
    测试拒绝非法 Authorization 头
  - test_authenticate_accepts_administrator_permission:
    测试系统管理员通配权限可调用预测接口
  - test_authenticate_maps_invalid_access_token:
    测试认证异常转换为服务认证错误
  - test_authenticate_maps_permission_denied:
    测试权限不足转换为服务授权错误
  - test_request_scope_handles_missing_client:
    测试请求未提供客户端地址时上下文 IP 为空
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.runtime.server.security as security_module
from datamind.auth.errors import AuthError, PermissionDeniedError
from datamind.constants import Environment
from datamind.context import get_context
from datamind.runtime.server.errors import (
    ServiceAuthenticationError,
    ServiceAuthenticationUnavailableError,
    ServiceAuthorizationError,
)
from datamind.runtime.server.security import RuntimeIdentity, RuntimeSecurity


def test_security_documentation_lists_public_components() -> None:
    """测试核心功能列出安全模块公共组件."""
    documentation = security_module.__doc__ or ""
    core_functions = documentation.partition("核心功能：")[2].partition(
        "使用示例："
    )[0]

    for name in (
        "RuntimeIdentity",
        "RuntimeRequestContext",
        "RuntimeSecurity",
        "request_scope",
        "authenticate",
    ):
        assert f"- {name}:" in core_functions


class ContextStub:
    """BentoML 请求上下文替身."""

    def __init__(self) -> None:
        self.request: Any = SimpleNamespace(
            headers={},
            client=SimpleNamespace(
                host="127.0.0.1"
            ),
            scope={},
        )


class FakeUnitOfWork:
    """运行时认证测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def configure_security(
        monkeypatch: pytest.MonkeyPatch,
        *,
        auth_enabled: bool,
        environment: Environment,
) -> None:
    """配置运行时安全边界所需的独立子配置."""
    monkeypatch.setitem(
        vars(security_module),
        "get_auth_config",
        lambda: SimpleNamespace(enabled=auth_enabled),
    )
    monkeypatch.setitem(
        vars(security_module),
        "get_service_config",
        lambda: SimpleNamespace(environment=environment),
    )


@pytest.mark.asyncio
async def test_production_rejects_disabled_auth(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试生产环境拒绝关闭认证."""
    configure_security(
        monkeypatch,
        auth_enabled=False,
        environment=Environment.PRODUCTION,
    )

    with pytest.raises(
            ServiceAuthenticationUnavailableError,
            match="必须启用认证",
    ):
        await RuntimeSecurity().authenticate(
            context=ContextStub(),
            permission="prediction.invoke",
        )


@pytest.mark.asyncio
async def test_testing_allows_local_anonymous_identity(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试测试环境允许本地匿名调试."""
    configure_security(
        monkeypatch,
        auth_enabled=False,
        environment=Environment.TESTING,
    )

    identity = await RuntimeSecurity().authenticate(
        context=ContextStub(),
        permission="prediction.invoke",
    )

    assert identity.username == "system"
    assert identity.authenticated is False


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Basic credentials",
        "Bearer",
        "Bearer   ",
    ],
)
def test_extract_bearer_token_rejects_invalid_header(
        authorization: str | None,
) -> None:
    """测试拒绝非法 Authorization 头."""
    with pytest.raises(
            ServiceAuthenticationError,
            match="Bearer",
    ):
        RuntimeSecurity._extract_bearer_token(
            authorization
        )


def test_extract_bearer_token_normalizes_valid_header() -> None:
    """测试解析 Bearer 令牌并去除两端空白."""
    assert RuntimeSecurity._extract_bearer_token(
        "bearer   access-token  "
    ) == "access-token"


@pytest.mark.asyncio
async def test_authenticate_validates_required_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已认证请求校验接口权限."""
    configure_security(
        monkeypatch,
        auth_enabled=True,
        environment=Environment.PRODUCTION,
    )
    user = SimpleNamespace(
        user_id="usr_test",
        username="alice",
        permissions=["prediction.invoke"],
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=user
    )
    require_permission = MagicMock()
    context = ContextStub()
    context.request.headers[
        "authorization"
    ] = "Bearer access-token"
    monkeypatch.setitem(
        vars(security_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(security_module),
        "create_auth_service",
        lambda **_kwargs: service,
    )
    monkeypatch.setitem(
        vars(security_module),
        "require_permission",
        require_permission,
    )

    identity = await RuntimeSecurity().authenticate(
        context=context,
        permission="prediction.invoke",
    )

    assert identity.username == "alice"
    assert identity.authenticated is True
    require_permission.assert_called_once_with(
        granted_permissions=["prediction.invoke"],
        required_permission="prediction.invoke",
    )


@pytest.mark.asyncio
async def test_authenticate_accepts_administrator_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试系统管理员通配权限可调用预测接口."""
    configure_security(
        monkeypatch,
        auth_enabled=True,
        environment=Environment.PRODUCTION,
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=SimpleNamespace(
            user_id="usr_admin",
            username="admin",
            permissions=["*"],
        )
    )
    context = ContextStub()
    context.request.headers[
        "authorization"
    ] = "Bearer access-token"
    monkeypatch.setitem(
        vars(security_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(security_module),
        "create_auth_service",
        lambda **_kwargs: service,
    )

    identity = await RuntimeSecurity().authenticate(
        context=context,
        permission="prediction.invoke",
    )

    assert identity.username == "admin"
    assert identity.permissions == ("*",)


@pytest.mark.asyncio
async def test_authenticate_maps_invalid_access_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证异常转换为服务认证错误."""
    configure_security(
        monkeypatch,
        auth_enabled=True,
        environment=Environment.PRODUCTION,
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        side_effect=AuthError("invalid token")
    )
    context = ContextStub()
    context.request.headers["authorization"] = "Bearer access-token"
    monkeypatch.setitem(
        vars(security_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(security_module),
        "create_auth_service",
        lambda **_kwargs: service,
    )

    with pytest.raises(
            ServiceAuthenticationError,
            match="访问令牌无效或已失效",
    ):
        await RuntimeSecurity().authenticate(
            context=context,
            permission="prediction.invoke",
        )


@pytest.mark.asyncio
async def test_authenticate_maps_permission_denied(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试权限不足转换为服务授权错误."""
    configure_security(
        monkeypatch,
        auth_enabled=True,
        environment=Environment.PRODUCTION,
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=SimpleNamespace(
            user_id="usr_test",
            username="alice",
            permissions=[],
        )
    )
    context = ContextStub()
    context.request.headers["authorization"] = "Bearer access-token"
    monkeypatch.setitem(
        vars(security_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(security_module),
        "create_auth_service",
        lambda **_kwargs: service,
    )
    monkeypatch.setitem(
        vars(security_module),
        "require_permission",
        MagicMock(
            side_effect=PermissionDeniedError()
        ),
    )

    with pytest.raises(
            ServiceAuthorizationError,
            match="缺少接口权限",
    ):
        await RuntimeSecurity().authenticate(
            context=context,
            permission="runtime.manage",
        )


@pytest.mark.asyncio
async def test_request_scope_establishes_trusted_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证请求作用域建立并恢复可信上下文."""
    security = RuntimeSecurity()
    identity = RuntimeIdentity(
        user_id="usr_test",
        username="alice",
        permissions=("prediction.invoke",),
        authenticated=True,
    )
    authenticate = AsyncMock(
        return_value=identity
    )
    monkeypatch.setattr(
        security,
        "authenticate",
        authenticate,
    )
    context = ContextStub()
    context.request.scope = {
        "trace_id": "trace_test",
        "invalid": 100,
    }

    async with security.request_scope(
            context=context,
            permission="prediction.invoke",
            request_id="req_test",
    ) as current_identity:
        request_context = get_context()

        assert current_identity is identity
        assert request_context["user"] == "alice"
        assert request_context["ip"] == "127.0.0.1"
        assert request_context["trace_id"] == "trace_test"
        assert request_context["request_id"] == "req_test"

    assert get_context().get("request_id") is None


@pytest.mark.asyncio
async def test_request_scope_handles_missing_client(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试请求未提供客户端地址时上下文 IP 为空."""
    security = RuntimeSecurity()
    monkeypatch.setattr(
        security,
        "authenticate",
        AsyncMock(return_value=RuntimeIdentity(
            user_id="usr_test",
            username="alice",
            permissions=("prediction.invoke",),
            authenticated=True,
        )),
    )
    context = ContextStub()
    context.request.client = None
    context.request.scope = {
        "trace_id": 100,
    }

    async with security.request_scope(
            context=context,
            permission="prediction.invoke",
            request_id="req_test",
    ):
        assert get_context()["ip"] is None
        assert get_context()["trace_id"] is None
