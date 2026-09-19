"""认证配置测试

验证 LOCAL 认证、JWT 和应急账户配置的默认值、环境变量和校验规则。

核心功能：
  - test_local_auth_config_defaults:
    验证本地认证配置默认值
  - test_local_auth_config_reads_environment:
    验证本地认证配置读取环境变量
  - test_local_auth_config_validates_parameters:
    验证本地认证配置拒绝非法参数
  - test_auth_config_defaults:
    验证认证服务配置默认值
  - test_auth_config_reads_environment:
    验证认证服务配置读取环境变量
  - test_auth_config_validates_parameters:
    验证认证服务配置拒绝非法参数
  - test_auth_configs_are_frozen:
    验证认证配置不可修改
  - test_auth_configs_ignore_extra_fields:
    验证认证配置忽略无关字段"""

from typing import Any

import pytest
from pydantic import (
    Field,
    ValidationError,
)
from pydantic_settings import SettingsConfigDict

from datamind.config.auth import (
    AuthConfig,
    LocalAuthConfig,
)


class IsolatedLocalAuthConfig(LocalAuthConfig):
    """隔离环境文件的本地认证配置"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUTH_LOCAL_",
        env_file=None,
        extra="ignore",
        frozen=True,
    )


class IsolatedAuthConfig(AuthConfig):
    """隔离环境文件的认证配置"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUTH_",
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    local: IsolatedLocalAuthConfig = Field(
        default_factory=IsolatedLocalAuthConfig
    )


def test_local_auth_config_defaults() -> None:
    """测试本地认证配置默认值"""
    config = IsolatedLocalAuthConfig()

    assert config.max_failed_login_attempts == 5
    assert config.lock_minutes == 30
    assert config.upgrade_password_hash is True
    assert config.break_glass_only is False
    assert config.allowed_networks == ()
    assert config.break_glass_access_token_expires_minutes == 15


def test_local_auth_config_reads_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地认证配置读取环境变量"""
    monkeypatch.setenv(
        "DATAMIND_AUTH_LOCAL_MAX_FAILED_LOGIN_ATTEMPTS",
        "8",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_LOCAL_LOCK_MINUTES",
        "45",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_LOCAL_UPGRADE_PASSWORD_HASH",
        "false",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_LOCAL_BREAK_GLASS_ONLY",
        "true",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS",
        '["10.0.0.0/8", "192.168.1.0/24"]',
    )

    config = IsolatedLocalAuthConfig()

    assert config.max_failed_login_attempts == 8
    assert config.lock_minutes == 45
    assert config.upgrade_password_hash is False
    assert config.break_glass_only is True
    assert config.allowed_networks == (
        "10.0.0.0/8",
        "192.168.1.0/24",
    )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {
                "max_failed_login_attempts": 0,
            },
            "max_failed_login_attempts 必须大于 0",
        ),
        (
            {
                "lock_minutes": 0,
            },
            "lock_minutes 必须大于 0",
        ),
        (
            {
                "break_glass_access_token_expires_minutes": 0,
            },
            "break_glass_access_token_expires_minutes 必须大于 0",
        ),
        (
            {
                "allowed_networks": [
                    "invalid-network",
                ],
            },
            "allowed_networks 包含无效网段",
        ),
    ],
)
def test_local_auth_config_validates_parameters(
        values: dict[str, Any],
        message: str,
) -> None:
    """测试本地认证配置拒绝非法参数"""
    with pytest.raises(
            ValidationError,
            match=message,
    ):
        IsolatedLocalAuthConfig.model_validate(
            values
        )


def test_auth_config_defaults() -> None:
    """测试认证服务配置默认值"""
    config = IsolatedAuthConfig()

    assert config.enabled is False
    assert config.secret_key.get_secret_value() == ""
    assert config.algorithm == "HS256"
    assert config.access_token_expires_minutes == 30
    assert config.refresh_token_expires_days == 7
    assert isinstance(
        config.local,
        IsolatedLocalAuthConfig,
    )


def test_auth_config_reads_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证服务配置读取环境变量"""
    monkeypatch.setenv(
        "DATAMIND_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_SECRET_KEY",
        "secure-test-secret",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ALGORITHM",
        "HS512",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ACCESS_TOKEN_EXPIRES_MINUTES",
        "60",
    )

    config = IsolatedAuthConfig()

    assert config.enabled is True
    assert config.secret_key.get_secret_value() == (
        "secure-test-secret"
    )
    assert config.algorithm == "HS512"
    assert config.access_token_expires_minutes == 60


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {
                "algorithm": " ",
            },
            "algorithm 不能为空",
        ),
        (
            {
                "access_token_expires_minutes": 0,
            },
            "access_token_expires_minutes 必须大于 0",
        ),
        (
            {
                "refresh_token_expires_days": 0,
            },
            "refresh_token_expires_days 必须大于 0",
        ),
        (
            {
                "enabled": True,
                "secret_key": "",
            },
            "启用认证功能时，secret_key 不能为空",
        ),
    ],
)
def test_auth_config_validates_parameters(
        values: dict[str, Any],
        message: str,
) -> None:
    """测试认证服务配置拒绝非法参数"""
    with pytest.raises(
            ValidationError,
            match=message,
    ):
        IsolatedAuthConfig.model_validate(
            values
        )


@pytest.mark.parametrize(
    "config",
    [
        IsolatedLocalAuthConfig(),
        IsolatedAuthConfig(),
    ],
)
def test_auth_configs_are_frozen(
        config: LocalAuthConfig | AuthConfig,
) -> None:
    """测试认证配置不可修改"""
    with pytest.raises(ValidationError):
        config.enabled = True  # type: ignore[attr-defined]


def test_auth_configs_ignore_extra_fields() -> None:
    """测试认证配置忽略无关字段"""
    config = IsolatedAuthConfig.model_validate({
        "unknown": "ignored",
    })

    assert not hasattr(
        config,
        "unknown",
    )
