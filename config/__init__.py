"""
配置模块

该模块集中管理应用程序的所有配置项，提供统一的配置访问接口。

主要功能:
    - 应用配置管理
    - 日志配置管理
    - 存储配置管理

导出内容:
    get_settings: 获取应用配置实例的函数
    LoggingConfig: 日志配置类
    StorageConfig: 存储配置类
    StorageType: 存储类型枚举
    LocalStorageConfig: 本地存储配置类
    MinIOStorageConfig: MinIO存储配置类
    S3StorageConfig: S3存储配置类
"""

from config.settings import get_settings
from config.logging_config import (
    LoggingConfig,
    LogLevel,
    LogFormat,
    RotationWhen,
    TimeZone,
    TimestampPrecision,
    EpochUnit,
    RotationStrategy
)
from config.storage_config import (
    StorageConfig,
    StorageType,
    LocalStorageConfig,
    MinIOStorageConfig,
    S3StorageConfig
)

__all__ = [
    'get_settings',
    'LoggingConfig',
    'LogLevel',
    'LogFormat',
    'RotationWhen',
    'TimeZone',
    'TimestampPrecision',
    'EpochUnit',
    'RotationStrategy',
    'StorageConfig',
    'StorageType',
    'LocalStorageConfig',
    'MinIOStorageConfig',
    'S3StorageConfig',
]