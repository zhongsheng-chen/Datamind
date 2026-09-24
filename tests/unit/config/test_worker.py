"""异步任务 Worker 配置测试.

验证 Worker 默认进程参数、参数校验和外部配置隔离行为。

核心功能：
  - test_task_worker_defaults:
    验证 Worker 默认进程参数
  - test_task_worker_rejects_invalid_values:
    验证拒绝无效 Worker 参数
"""

from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.worker import TaskWorkerConfig
from datamind.constants import LogLevel


class IsolatedTaskWorkerConfig(TaskWorkerConfig):
    """仅使用初始化参数的测试 Worker 配置."""

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源."""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
        return (init_settings,)


def create_config(**overrides: Any) -> TaskWorkerConfig:
    """创建隔离的 Worker 配置."""
    return IsolatedTaskWorkerConfig(**overrides)


def test_task_worker_defaults() -> None:
    """测试 Worker 默认进程参数."""
    config = create_config()

    assert config.name == "datamind-task-worker"
    assert config.role == "all"
    assert config.concurrency == 1
    assert config.log_level is LogLevel.INFO


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "invalid@name"),
        ("concurrency", 0),
        ("log_level", "TRACE"),
        ("role", "unknown"),
    ],
)
def test_task_worker_rejects_invalid_values(
        field: str,
        value: Any,
) -> None:
    """测试拒绝无效 Worker 参数."""
    with pytest.raises(ValidationError):
        create_config(**{field: value})
