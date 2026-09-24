"""子配置加载入口.

集中封装 Pydantic Settings 的加载细节，为业务模块提供按配置域读取的
稳定接口。Provider 每次读取当前配置源，需要进程级配置快照的组装层仍由
get_settings 负责缓存。

核心功能：
  - get_service_config: 加载服务配置
  - get_auth_config: 加载认证配置
  - get_storage_config: 加载存储配置
  - get_runtime_config: 加载运行时配置
  - get_task_queue_config: 加载任务队列配置
  - get_task_worker_config: 加载任务 Worker 配置
  - 其他 get_xxx_config: 加载对应的独立配置域

使用示例：
  from datamind.config import (
      get_auth_config,
      get_service_config,
  )

  auth_config = get_auth_config()
  service_config = get_service_config()

  print(auth_config.enabled)
  print(service_config.environment)
"""

from typing import TypeVar

from pydantic_settings import BaseSettings

from datamind.config.audit import AuditConfig
from datamind.config.auth import AuthConfig
from datamind.config.classification import ClassificationConfig
from datamind.config.console import ConsoleConfig
from datamind.config.database import DatabaseConfig
from datamind.config.initialization import InitializationConfig
from datamind.config.logging import LoggingConfig
from datamind.config.queue import TaskQueueConfig
from datamind.config.runtime import RuntimeConfig
from datamind.config.scoring import ScoringConfig
from datamind.config.service import ServiceConfig
from datamind.config.storage import StorageConfig
from datamind.config.worker import TaskWorkerConfig


ConfigT = TypeVar("ConfigT", bound=BaseSettings)


def _load_config(config_type: type[ConfigT]) -> ConfigT:
    """从配置源加载指定的 Pydantic Settings 模型."""
    return config_type.model_validate({})


def get_audit_config() -> AuditConfig:
    """加载审计配置."""
    return _load_config(AuditConfig)


def get_auth_config() -> AuthConfig:
    """加载认证配置."""
    return _load_config(AuthConfig)


def get_classification_config() -> ClassificationConfig:
    """加载分类配置."""
    return _load_config(ClassificationConfig)


def get_console_config() -> ConsoleConfig:
    """加载控制台配置."""
    return _load_config(ConsoleConfig)


def get_database_config() -> DatabaseConfig:
    """加载数据库配置."""
    return _load_config(DatabaseConfig)


def get_initialization_config() -> InitializationConfig:
    """加载系统初始化配置."""
    return _load_config(InitializationConfig)


def get_logging_config() -> LoggingConfig:
    """加载日志配置."""
    return _load_config(LoggingConfig)


def get_runtime_config() -> RuntimeConfig:
    """加载运行时配置."""
    return _load_config(RuntimeConfig)


def get_scoring_config() -> ScoringConfig:
    """加载评分配置."""
    return _load_config(ScoringConfig)


def get_service_config() -> ServiceConfig:
    """加载服务配置."""
    return _load_config(ServiceConfig)


def get_storage_config() -> StorageConfig:
    """加载存储配置."""
    return _load_config(StorageConfig)


def get_task_queue_config() -> TaskQueueConfig:
    """加载异步任务队列配置."""
    return _load_config(TaskQueueConfig)


def get_task_worker_config() -> TaskWorkerConfig:
    """加载异步任务 Worker 配置."""
    return _load_config(TaskWorkerConfig)


__all__ = [
    "get_audit_config",
    "get_auth_config",
    "get_classification_config",
    "get_console_config",
    "get_database_config",
    "get_initialization_config",
    "get_logging_config",
    "get_runtime_config",
    "get_scoring_config",
    "get_service_config",
    "get_storage_config",
    "get_task_queue_config",
    "get_task_worker_config",
]
