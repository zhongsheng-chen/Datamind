"""认证工厂测试.

验证认证工厂仅创建 LOCAL 认证服务，并执行生产网络安全校验。

核心功能：
  - test_create_auth_service_rejects_disabled_auth:
    验证认证功能停用时拒绝创建服务
  - test_protected_environment_requires_allowed_networks:
    验证预发布和生产环境必须配置允许网段
  - test_create_auth_service_builds_local_dependencies:
    验证认证工厂创建并配置本地认证服务
  - test_production_does_not_force_break_glass_mode:
    验证生产环境允许配置普通本地用户登录"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

import datamind.auth.factory as factory_module
from datamind.auth.errors import AuthError
from datamind.auth.providers import LocalAuthProvider
from datamind.constants import Environment


def create_settings(
        *,
        enabled: bool = True,
        environment: Environment = Environment.DEVELOPMENT,
        allowed_networks: tuple[str, ...] = (),
        break_glass_only: bool = False,
) -> SimpleNamespace:
    """创建认证工厂测试配置."""
    local = SimpleNamespace(
        max_failed_login_attempts=7,
        lock_minutes=45,
        upgrade_password_hash=False,
        break_glass_only=break_glass_only,
        allowed_networks=allowed_networks,
        break_glass_access_token_expires_minutes=10,
    )
    auth = SimpleNamespace(
        enabled=enabled,
        secret_key=SecretStr("secure-test-secret"),
        algorithm="HS512",
        access_token_expires_minutes=60,
        refresh_token_expires_days=14,
        local=local,
    )

    return SimpleNamespace(
        auth=auth,
        service=SimpleNamespace(
            environment=environment
        ),
    )


def install_settings(
        monkeypatch: pytest.MonkeyPatch,
        settings: SimpleNamespace,
) -> None:
    """替换认证工厂使用的独立子配置."""
    monkeypatch.setitem(
        vars(factory_module),
        "get_auth_config",
        lambda: settings.auth,
    )
    monkeypatch.setitem(
        vars(factory_module),
        "get_service_config",
        lambda: settings.service,
    )


def test_create_auth_service_rejects_disabled_auth(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证功能停用时拒绝创建服务."""
    install_settings(
        monkeypatch,
        create_settings(
            enabled=False
        ),
    )

    with pytest.raises(
            AuthError,
            match="认证功能未启用",
    ):
        factory_module.create_auth_service(
            session=MagicMock()
        )


@pytest.mark.parametrize(
    "environment",
    [
        Environment.STAGING,
        Environment.PRODUCTION,
    ],
)
def test_protected_environment_requires_allowed_networks(
        monkeypatch: pytest.MonkeyPatch,
        environment: Environment,
) -> None:
    """测试预发布和生产环境必须配置允许网段."""
    install_settings(
        monkeypatch,
        create_settings(
            environment=environment
        ),
    )

    with pytest.raises(
            AuthError,
            match="必须配置 allowed_networks",
    ):
        factory_module.create_auth_service(
            session=MagicMock()
        )


def test_create_auth_service_builds_local_dependencies(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证工厂创建并配置本地认证服务."""
    settings = create_settings(
        environment=Environment.PRODUCTION,
        allowed_networks=(
            "10.0.0.0/8",
        ),
    )
    install_settings(
        monkeypatch,
        settings,
    )
    session = MagicMock()
    repositories: dict[str, MagicMock] = {}

    for name in (
            "UserRepository",
            "RoleRepository",
            "GrantRepository",
            "TokenRepository",
    ):
        repository = MagicMock(
            name=name
        )
        repositories[name] = repository
        monkeypatch.setitem(
            vars(factory_module),
            name,
            lambda received_session, repo=repository: (
                repo
                if received_session is session
                else None
            ),
        )

    captured: dict[str, object] = {}

    def create_service(
            **kwargs: object,
    ) -> MagicMock:
        captured.update(
            kwargs
        )
        return MagicMock()

    monkeypatch.setitem(
        vars(factory_module),
        "AuthService",
        create_service,
    )

    factory_module.create_auth_service(
        session=session
    )

    provider = captured["provider"]
    assert isinstance(
        provider,
        LocalAuthProvider,
    )
    assert provider.user_repo is repositories[
        "UserRepository"
    ]
    assert provider.config.max_failed_login_attempts == 7
    assert provider.config.lock_minutes == 45
    assert provider.config.upgrade_password_hash is False
    assert provider.config.break_glass_only is False
    assert captured["secret_key"] == "secure-test-secret"
    assert captured["algorithm"] == "HS512"
    assert captured["local_allowed_networks"] == (
        "10.0.0.0/8",
    )


def test_production_does_not_force_break_glass_mode(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试生产环境允许配置普通本地用户登录."""
    settings = create_settings(
        environment=Environment.PRODUCTION,
        allowed_networks=(
            "10.0.0.0/8",
        ),
        break_glass_only=False,
    )
    install_settings(
        monkeypatch,
        settings,
    )

    service = factory_module.create_auth_service(
        session=MagicMock()
    )

    assert isinstance(
        service.provider,
        LocalAuthProvider,
    )
    assert service.provider.config.break_glass_only is False
