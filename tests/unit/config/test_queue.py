"""异步任务队列配置测试.

验证 Broker 与任务队列默认值、参数校验和队列隔离约束。

核心功能：
  - test_task_queue_defaults_use_separate_queues:
    验证默认 Broker 和任务队列配置
  - test_task_queue_rejects_invalid_values:
    验证拒绝无效任务队列参数
  - test_task_queue_rejects_shared_queue_name:
    验证批量预测与影子预测使用不同队列
"""

from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.queue import TaskQueueConfig


class IsolatedTaskQueueConfig(TaskQueueConfig):
    """仅使用初始化参数的测试任务队列配置."""

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


def create_config(**overrides: Any) -> TaskQueueConfig:
    """创建隔离的任务队列配置."""
    return IsolatedTaskQueueConfig(**overrides)


def test_task_queue_defaults_use_separate_queues() -> None:
    """测试默认 Broker 和任务队列配置."""
    config = create_config()

    assert config.broker_url == "redis://localhost:6379/0"
    assert config.batch_queue == "prediction.batch"
    assert config.shadow_queue == "prediction.shadow"
    assert config.batch_queue != config.shadow_queue
    assert config.max_retries == 3
    assert config.batch_chunk_size == 20


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("broker_url", ""),
        ("batch_queue", ""),
        ("shadow_queue", ""),
        ("max_retries", -1),
        ("batch_chunk_size", 0),
        ("retry_backoff_seconds", 0),
        ("visibility_timeout_seconds", 0),
    ],
)
def test_task_queue_rejects_invalid_values(
        field: str,
        value: Any,
) -> None:
    """测试拒绝无效任务队列参数."""
    with pytest.raises(ValidationError):
        create_config(**{field: value})


def test_task_queue_rejects_shared_queue_name() -> None:
    """测试批量预测与影子预测使用不同队列."""
    with pytest.raises(
        ValidationError,
        match="必须使用不同队列",
    ):
        create_config(
            batch_queue="prediction",
            shadow_queue="prediction",
        )
