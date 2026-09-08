"""系统初始化配置测试

验证管理员初始化凭据的默认值、环境变量读取和用户名校验。

核心功能：
  - test_initialization_config_defaults:
    验证默认管理员用户名和密码
  - test_initialization_config_reads_environment:
    验证从环境变量读取管理员凭据
  - test_initialization_config_normalizes_username:
    验证管理员用户名规范化
  - test_initialization_config_rejects_blank_username:
    验证拒绝空管理员用户名
"""

import pytest

from datamind.config.initialization import InitializationConfig


class IsolatedInitializationConfig(InitializationConfig):
    """不读取项目 .env 的初始化配置"""

    model_config = InitializationConfig.model_config | {
        "env_file": None,
    }


def test_initialization_config_defaults(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试默认管理员用户名和密码"""
    monkeypatch.delenv(
        "DATAMIND_INIT_ADMIN_USERNAME",
        raising=False,
    )
    monkeypatch.delenv(
        "DATAMIND_INIT_ADMIN_PASSWORD",
        raising=False,
    )

    config = IsolatedInitializationConfig()

    assert config.admin_username == "admin"
    assert (
        config.admin_password.get_secret_value()
        == "admin"
    )


def test_initialization_config_reads_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取管理员凭据"""
    monkeypatch.setenv(
        "DATAMIND_INIT_ADMIN_USERNAME",
        "platform-admin",
    )
    monkeypatch.setenv(
        "DATAMIND_INIT_ADMIN_PASSWORD",
        "strong-secret",
    )

    config = IsolatedInitializationConfig()

    assert config.admin_username == "platform-admin"
    assert (
        config.admin_password.get_secret_value()
        == "strong-secret"
    )


def test_initialization_config_normalizes_username() -> None:
    """测试管理员用户名规范化"""
    config = IsolatedInitializationConfig(
        admin_username="  admin  "
    )

    assert config.admin_username == "admin"


def test_initialization_config_rejects_blank_username() -> None:
    """测试拒绝空管理员用户名"""
    with pytest.raises(
            ValueError,
            match="admin_username 不能为空",
    ):
        IsolatedInitializationConfig(
            admin_username="   "
        )
