"""配置总入口测试.

验证 Settings 对全部子配置的聚合，以及 get_settings 的
单例缓存、缓存清理和环境变量重新加载行为。

核心功能：
  - test_settings_contains_all_child_configs:
    验证配置总入口聚合全部子配置
  - test_settings_annotations_match_child_configs:
    验证配置总入口类型标注
  - test_direct_settings_creation_returns_independent_instances:
    验证直接创建的 Settings 实例相互独立
  - test_get_settings_returns_cached_singleton:
    验证 get_settings 返回缓存单例
  - test_get_settings_cache_clear_creates_new_instance:
    验证清理缓存后创建新实例
  - test_get_settings_reads_environment_on_first_call:
    验证首次调用读取环境变量
  - test_get_settings_keeps_cached_values_after_environment_changes:
    验证缓存后环境变量变化不影响现有实例
  - test_get_settings_reloads_environment_after_cache_clear:
    验证清理缓存后重新读取环境变量
  - test_get_settings_reloads_database_url_after_cache_clear:
    验证清理缓存后重新读取数据库地址
  - test_get_settings_cache_statistics:
    验证 get_settings 缓存统计
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import (
    Final,
    get_type_hints,
)

import pytest

from datamind.config.audit import AuditConfig
from datamind.config.auth import AuthConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.console import ConsoleConfig
from datamind.config.database import DatabaseConfig
from datamind.config.initialization import InitializationConfig
from datamind.config.logging import LoggingConfig
from datamind.config.runtime import RuntimeConfig
from datamind.config.scoring import ScoringConfig
from datamind.config.service import ServiceConfig
from datamind.config.settings import (
    Settings,
    get_settings,
)
from datamind.config.storage import StorageConfig
from datamind.config.queue import TaskQueueConfig
from datamind.config.worker import TaskWorkerConfig
from datamind.constants import Environment


DATABASE_URL: Final[str] = (
    "postgresql+asyncpg://"
    "datamind:password@localhost:5432/datamind"
)
CONFIG_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "DATAMIND_AUDIT_",
    "DATAMIND_AUTH_",
    "DATAMIND_CLASSIFICATION_",
    "DATAMIND_CONSOLE_",
    "DATAMIND_DATABASE_",
    "DATAMIND_INIT_",
    "DATAMIND_LOG_",
    "DATAMIND_RUNTIME_",
    "DATAMIND_SCORING_",
    "DATAMIND_SERVICE_",
    "DATAMIND_STORAGE_",
    "DATAMIND_TASK_QUEUE_",
    "DATAMIND_TASK_WORKER_",
)


@pytest.fixture(autouse=True)
def isolate_settings(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> Iterator[None]:
    """隔离配置环境变量、.env 文件和全局缓存."""
    get_settings.cache_clear()

    for key in tuple(os.environ):
        if key.startswith(CONFIG_ENV_PREFIXES):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL",
        DATABASE_URL,
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "development",
    )

    yield

    get_settings.cache_clear()


def test_settings_contains_all_child_configs() -> None:
    """测试配置总入口聚合全部子配置."""
    settings = Settings()

    assert isinstance(
        settings.database,
        DatabaseConfig,
    )
    assert isinstance(
        settings.storage,
        StorageConfig,
    )
    assert isinstance(
        settings.initialization,
        InitializationConfig,
    )
    assert isinstance(
        settings.logging,
        LoggingConfig,
    )
    assert isinstance(
        settings.audit,
        AuditConfig,
    )
    assert isinstance(
        settings.auth,
        AuthConfig,
    )
    assert isinstance(
        settings.classification,
        ClassificationConfig,
    )
    assert isinstance(
        settings.scoring,
        ScoringConfig,
    )
    assert isinstance(
        settings.console,
        ConsoleConfig,
    )
    assert isinstance(
        settings.service,
        ServiceConfig,
    )
    assert isinstance(
        settings.runtime,
        RuntimeConfig,
    )
    assert isinstance(
        settings.task_queue,
        TaskQueueConfig,
    )
    assert isinstance(
        settings.task_worker,
        TaskWorkerConfig,
    )


def test_settings_annotations_match_child_configs() -> None:
    """测试配置总入口类型标注完整且准确."""
    assert get_type_hints(Settings) == {
        "database": DatabaseConfig,
        "initialization": InitializationConfig,
        "storage": StorageConfig,
        "logging": LoggingConfig,
        "audit": AuditConfig,
        "auth": AuthConfig,
        "classification": ClassificationConfig,
        "scoring": ScoringConfig,
        "console": ConsoleConfig,
        "service": ServiceConfig,
        "runtime": RuntimeConfig,
        "task_queue": TaskQueueConfig,
        "task_worker": TaskWorkerConfig,
    }


def test_direct_settings_creation_returns_independent_instances() -> None:
    """测试直接创建的 Settings 实例相互独立."""
    first = Settings()
    second = Settings()

    assert first is not second
    assert first.database is not second.database
    assert first.initialization is not second.initialization
    assert first.storage is not second.storage
    assert first.logging is not second.logging
    assert first.audit is not second.audit
    assert first.auth is not second.auth
    assert first.auth.local is not second.auth.local
    assert first.classification is not second.classification
    assert first.scoring is not second.scoring
    assert first.console is not second.console
    assert first.service is not second.service
    assert first.runtime is not second.runtime
    assert first.task_queue is not second.task_queue
    assert first.task_worker is not second.task_worker


def test_get_settings_returns_cached_singleton() -> None:
    """测试 get_settings 返回缓存单例."""
    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.auth is second.auth


def test_get_settings_cache_clear_creates_new_instance() -> None:
    """测试清理缓存后创建新实例."""
    first = get_settings()

    get_settings.cache_clear()

    second = get_settings()

    assert second is not first
    assert second.database is not first.database
    assert second.auth is not first.auth
    assert second.console is not first.console
    assert second.service is not first.service


def test_get_settings_reads_environment_on_first_call(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次调用读取各子配置环境变量."""
    monkeypatch.setenv(
        "DATAMIND_DATABASE_POOL_SIZE",
        "25",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_SECRET_KEY",
        "test-jwt-secret",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ACCESS_TOKEN_EXPIRES_MINUTES",
        "60",
    )
    monkeypatch.setenv(
        "DATAMIND_CLASSIFICATION_THRESHOLD",
        "0.65",
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "production",
    )
    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "3100",
    )
    monkeypatch.setenv(
        "DATAMIND_CONSOLE_PORT",
        "4100",
    )

    settings = get_settings()

    assert settings.database.url == DATABASE_URL
    assert settings.database.pool_size == 25
    assert settings.auth.enabled is True
    assert settings.auth.secret_key.get_secret_value() == "test-jwt-secret"
    assert settings.auth.access_token_expires_minutes == 60
    assert settings.classification.threshold == 0.65
    assert settings.service.environment == Environment.PRODUCTION
    assert settings.service.port == 3100
    assert settings.console.port == 4100


def test_get_settings_keeps_cached_values_after_environment_changes(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试缓存后环境变量变化不影响现有实例."""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "3100",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ALGORITHM",
        "HS256",
    )
    first = get_settings()

    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "3200",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_ALGORITHM",
        "HS512",
    )
    second = get_settings()

    assert second is first
    assert second.service.port == 3100
    assert second.auth.algorithm == "HS256"


def test_get_settings_reloads_environment_after_cache_clear(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试清理缓存后重新读取环境变量."""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "3100",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_REFRESH_TOKEN_EXPIRES_DAYS",
        "7",
    )
    first = get_settings()

    monkeypatch.setenv(
        "DATAMIND_SERVICE_PORT",
        "3200",
    )
    monkeypatch.setenv(
        "DATAMIND_AUTH_REFRESH_TOKEN_EXPIRES_DAYS",
        "14",
    )
    get_settings.cache_clear()

    second = get_settings()

    assert second is not first
    assert first.service.port == 3100
    assert second.service.port == 3200
    assert first.auth.refresh_token_expires_days == 7
    assert second.auth.refresh_token_expires_days == 14


def test_get_settings_reloads_database_url_after_cache_clear(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试清理缓存后重新读取数据库地址."""
    first = get_settings()
    changed_url = (
        "postgresql+asyncpg://"
        "datamind:changed@localhost:5432/datamind_test"
    )

    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL",
        changed_url,
    )
    get_settings.cache_clear()

    second = get_settings()

    assert first.database.url == DATABASE_URL
    assert second.database.url == changed_url


def test_get_settings_cache_statistics() -> None:
    """测试 get_settings 缓存统计."""
    get_settings()
    get_settings()

    cache_info = get_settings.cache_info()

    assert cache_info.maxsize == 1
    assert cache_info.misses == 1
    assert cache_info.hits == 1
    assert cache_info.currsize == 1
