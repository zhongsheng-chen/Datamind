# tests/cli/test_common.py

"""CLI 公共上下文测试

验证生产环境认证保护和访问令牌身份绑定。

核心功能：
  - test_cli_context_uses_configured_logging:
    验证 CLI 上下文使用原始日志配置
  - test_cli_context_requires_auth_in_production:
    验证生产环境不能关闭认证
  - test_cli_context_uses_authenticated_identity:
    验证访问令牌身份和权限写入 CLI 上下文
  - test_cli_context_uses_stored_credentials:
    验证读取本地 CLI 登录凭据
  - test_cli_context_refreshes_expired_access_token:
    验证访问令牌失效后自动续期
  - test_cli_context_rejects_missing_permission:
    验证拒绝缺少命令权限的用户
  - test_cli_context_allows_development_maintenance_mode:
    验证开发环境关闭认证时允许本地维护
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import typer

import datamind.cli.common as common_module
from datamind.auth.errors import InvalidAccessTokenError
from datamind.auth.schemas import TokenResponse
from datamind.cli.common import CLIContext
from datamind.cli.credentials import CLICredentials
from datamind.constants import Environment
from datamind.context import get_context


class FakeUnitOfWork:
    """CLI 认证测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_settings(
        *,
        auth_enabled: bool,
        environment: Environment,
) -> SimpleNamespace:
    """创建 CLI 测试配置"""
    logging_config = MagicMock()
    logging_config.model_copy.return_value = logging_config

    return SimpleNamespace(
        auth=SimpleNamespace(
            enabled=auth_enabled
        ),
        service=SimpleNamespace(
            environment=environment
        ),
        logging=logging_config,
    )


def patch_common_module(
        monkeypatch: pytest.MonkeyPatch,
        **replacements: object,
) -> None:
    """替换 CLI 公共模块依赖"""
    replacements.setdefault(
        "setup_logging",
        lambda _config: None,
    )

    for name, value in replacements.items():
        monkeypatch.setitem(
            vars(common_module),
            name,
            value,
        )


@pytest.mark.asyncio
async def test_cli_context_uses_configured_logging(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 CLI 上下文使用原始日志配置"""
    settings = create_settings(
        auth_enabled=False,
        environment=Environment.DEVELOPMENT,
    )
    logging_config = settings.logging
    setup_logging = MagicMock()
    patch_common_module(
        monkeypatch,
        get_settings=lambda: settings,
        setup_logging=setup_logging,
    )

    async with CLIContext(
        ip="127.0.0.1",
        hostname="host",
    ):
        pass

    setup_logging.assert_called_once_with(
        logging_config
    )


@pytest.mark.asyncio
async def test_cli_context_requires_auth_in_production(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试生产环境不能关闭认证"""
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=False,
            environment=Environment.PRODUCTION,
        ),
    )
    context = CLIContext(
        ip="127.0.0.1",
        hostname="host",
    )

    with pytest.raises(
            typer.Exit,
    ):
        await context.__aenter__()


@pytest.mark.asyncio
async def test_cli_context_uses_authenticated_identity(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试访问令牌身份写入 CLI 上下文"""
    store_factory = MagicMock()
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=SimpleNamespace(
            username="alice",
            permissions=[
                "model.read"
            ],
        )
    )
    monkeypatch.setenv(
        "DATAMIND_ACCESS_TOKEN",
        "access-token",
    )
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=True,
            environment=Environment.PRODUCTION,
        ),
        UnitOfWork=FakeUnitOfWork,
        create_auth_service=lambda **_kwargs: service,
        CredentialStore=store_factory,
        setup_logging=lambda _config: None,
    )

    async with CLIContext(
            required_permission="model.read",
            ip="127.0.0.1",
            hostname="host",
    ) as context:
        assert context.user == "alice"
        assert get_context()["user"] == "alice"

    service.authenticate_access_token.assert_awaited_once_with(
        "access-token"
    )
    store_factory.assert_not_called()


@pytest.mark.asyncio
async def test_cli_context_uses_stored_credentials(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证上下文读取本地 CLI 登录凭据"""
    authenticated_user = SimpleNamespace(
        username="alice",
        permissions=[
            "model.read"
        ],
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=authenticated_user
    )
    store = MagicMock()
    store.load.return_value = CLICredentials(
        access_token="stored-access-token",
        refresh_token="stored-refresh-token",
    )
    monkeypatch.delenv(
        "DATAMIND_ACCESS_TOKEN",
        raising=False,
    )
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=True,
            environment=Environment.PRODUCTION,
        ),
        UnitOfWork=FakeUnitOfWork,
        create_auth_service=lambda **_kwargs: service,
        CredentialStore=lambda: store,
        setup_logging=lambda _config: None,
    )

    async with CLIContext(
            required_permission="model.read",
            ip="127.0.0.1",
            hostname="host",
    ) as context:
        assert context.user == "alice"

    service.authenticate_access_token.assert_awaited_once_with(
        "stored-access-token"
    )
    service.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_cli_context_refreshes_expired_access_token(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试访问令牌失效后自动轮换并保存登录凭据"""
    authenticated_user = SimpleNamespace(
        username="alice",
        permissions=[
            "model.read"
        ],
    )
    refreshed_tokens = TokenResponse(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        expires_in=1800,
    )
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        side_effect=[
            InvalidAccessTokenError(),
            authenticated_user,
        ]
    )
    service.refresh = AsyncMock(
        return_value=refreshed_tokens
    )
    store = MagicMock()
    store.load.return_value = CLICredentials(
        access_token="expired-access-token",
        refresh_token="refresh-token",
    )
    monkeypatch.delenv(
        "DATAMIND_ACCESS_TOKEN",
        raising=False,
    )
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=True,
            environment=Environment.PRODUCTION,
        ),
        UnitOfWork=FakeUnitOfWork,
        create_auth_service=lambda **_kwargs: service,
        CredentialStore=lambda: store,
        setup_logging=lambda _config: None,
    )

    async with CLIContext(
            required_permission="model.read",
            ip="127.0.0.1",
            hostname="host",
    ) as context:
        assert context.user == "alice"

    refresh_call = service.refresh.await_args
    assert refresh_call is not None
    refresh_request = refresh_call.args[0]
    assert refresh_request.refresh_token.get_secret_value() == (
        "refresh-token"
    )
    assert refresh_call.kwargs == {
        "ip": "127.0.0.1",
        "hostname": "host",
        "user_agent": "datamind-cli",
    }
    store.save.assert_called_once_with(
        refreshed_tokens
    )


@pytest.mark.asyncio
async def test_cli_context_requires_login_without_credentials(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证开启且没有本地凭据时要求登录"""
    store = MagicMock()
    store.load.return_value = None
    monkeypatch.delenv(
        "DATAMIND_ACCESS_TOKEN",
        raising=False,
    )
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=True,
            environment=Environment.PRODUCTION,
        ),
        CredentialStore=lambda: store,
    )
    context = CLIContext(
        required_permission="model.read",
        ip="127.0.0.1",
        hostname="host",
    )

    with pytest.raises(
            typer.Exit,
    ):
        await context.__aenter__()


@pytest.mark.asyncio
async def test_cli_context_rejects_missing_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝缺少命令权限的认证用户"""
    service = MagicMock()
    service.authenticate_access_token = AsyncMock(
        return_value=SimpleNamespace(
            username="alice",
            permissions=[
                "model.read"
            ],
        )
    )
    monkeypatch.setenv(
        "DATAMIND_ACCESS_TOKEN",
        "access-token",
    )
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=True,
            environment=Environment.PRODUCTION,
        ),
        UnitOfWork=FakeUnitOfWork,
        create_auth_service=lambda **_kwargs: service,
    )
    context = CLIContext(
        required_permission="model.write",
        ip="127.0.0.1",
        hostname="host",
    )

    with pytest.raises(
            typer.Exit,
    ):
        await context.__aenter__()


@pytest.mark.asyncio
async def test_cli_context_allows_development_maintenance_mode(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试开发环境关闭认证时允许本地维护"""
    patch_common_module(
        monkeypatch,
        get_settings=lambda: create_settings(
            auth_enabled=False,
            environment=Environment.DEVELOPMENT,
        ),
        setup_logging=lambda _config: None,
    )

    async with CLIContext(
            required_permission="model.delete",
            ip="127.0.0.1",
            hostname="host",
    ) as context:
        assert context.user == "system"
        assert context.authenticated_user is None
        assert get_context()["user"] == "system"
