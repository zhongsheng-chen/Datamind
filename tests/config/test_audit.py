# tests/config/test_audit.py

"""审计配置测试

验证审计开关、失败策略、重试参数、环境变量读取、
参数校验和配置不可变行为。

核心功能：
  - test_audit_config_defaults:
    验证审计配置默认值
  - test_audit_config_reads_environment:
    验证从环境变量读取并转换审计配置
  - test_audit_config_accepts_custom_values:
    验证接受有效的自定义配置
  - test_audit_config_rejects_invalid_values:
    验证拒绝非法重试参数
  - test_audit_config_is_frozen:
    验证审计配置创建后不可修改
"""

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.audit.policy import AuditFailureMode
from datamind.config.audit import AuditConfig


class IsolatedAuditConfig(AuditConfig):
    """仅使用初始化参数和字段默认值的测试审计配置"""

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源"""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        return (init_settings,)


@pytest.fixture(autouse=True)
def clear_audit_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清除审计配置环境变量"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_AUDIT_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )


def create_config(
        **overrides: Any,
) -> AuditConfig:
    """创建隔离外部配置源的审计配置"""
    return IsolatedAuditConfig(**overrides)


def test_audit_config_defaults() -> None:
    """测试默认配置"""
    config = create_config()

    assert config.enabled is True
    assert config.failure_mode is AuditFailureMode.OPEN
    assert config.max_retries == 2
    assert config.retry_base_delay == 0.05


def test_audit_config_reads_environment(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试从环境变量读取配置"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATAMIND_AUDIT_ENABLED", "false")
    monkeypatch.setenv("DATAMIND_AUDIT_FAILURE_MODE", "closed")
    monkeypatch.setenv("DATAMIND_AUDIT_MAX_RETRIES", "4")
    monkeypatch.setenv("DATAMIND_AUDIT_RETRY_BASE_DELAY", "0.2")

    config = AuditConfig()

    assert config.enabled is False
    assert config.failure_mode is AuditFailureMode.CLOSED
    assert config.max_retries == 4
    assert config.retry_base_delay == 0.2


def test_audit_config_accepts_custom_values() -> None:
    """测试接受有效自定义值"""
    config = create_config(
        enabled=False,
        failure_mode=AuditFailureMode.CLOSED,
        max_retries=3,
        retry_base_delay=0.1,
    )

    assert config.enabled is False
    assert config.failure_mode is AuditFailureMode.CLOSED
    assert config.max_retries == 3
    assert config.retry_base_delay == 0.1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_retries", 0, "max_retries 必须大于等于 1"),
        ("retry_base_delay", 0, "retry_base_delay 必须大于 0"),
    ],
)
def test_audit_config_rejects_invalid_values(
        field: str,
        value: int | float,
        message: str,
) -> None:
    """测试拒绝无效配置"""
    with pytest.raises(ValidationError, match=message):
        create_config(**{field: value})


def test_audit_config_is_frozen() -> None:
    """测试配置不可修改"""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "enabled", False)
