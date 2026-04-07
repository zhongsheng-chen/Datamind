# datamind/config/manager.py

"""配置管理器

提供线程安全的配置懒加载和热重载能力。

核心功能：
  - get_settings: 懒加载获取完整配置实例
  - get_logging_config: 懒加载获取日志配置实例
  - get_storage_config: 懒加载获取存储配置实例
  - get_scorecard_config: 懒加载获取评分卡配置实例
  - reload_settings: 热重载所有配置
  - reload_logging_config: 热重载日志配置
  - reload_storage_config: 热重载存储配置
  - reload_scorecard_config: 热重载评分卡配置
  - reload_all_configs: 热重载所有配置

特性：
  - 双重检查锁：线程安全的单例模式
  - 懒加载：配置在首次使用时才初始化
  - 支持热重载：可动态刷新配置（如环境变量变更后）
  - 配置隔离：各配置独立管理，互不影响
  - 独立环境变量：每个配置类使用自己的环境变量前缀
"""

from threading import RLock
from typing import Optional

from .settings import Settings
from .logging_config import LoggingConfig
from .storage_config import StorageConfig
from .scorecard_config import ScorecardDefaultConfig

_lock = RLock()

# 配置实例缓存
_settings_instance: Optional[Settings] = None
_logging_instance: Optional[LoggingConfig] = None
_storage_instance: Optional[StorageConfig] = None
_scorecard_instance: Optional[ScorecardDefaultConfig] = None


def _get_or_create_settings() -> Settings:
    """线程安全的懒加载获取 Settings 实例

    使用双重检查锁（DCL）模式，保证：
      - 首次调用时创建实例
      - 后续调用直接返回缓存实例
      - 多线程环境下不会重复创建

    返回:
        Settings 实例
    """
    global _settings_instance
    if _settings_instance is None:
        with _lock:
            if _settings_instance is None:
                _settings_instance = Settings()
    return _settings_instance


def _get_or_create_logging() -> LoggingConfig:
    """线程安全的懒加载获取 LoggingConfig 实例"""
    global _logging_instance
    if _logging_instance is None:
        with _lock:
            if _logging_instance is None:
                _logging_instance = LoggingConfig.from_env()
    return _logging_instance


def _get_or_create_storage() -> StorageConfig:
    """线程安全的懒加载获取 StorageConfig 实例"""
    global _storage_instance
    if _storage_instance is None:
        with _lock:
            if _storage_instance is None:
                _storage_instance = StorageConfig.from_env()
    return _storage_instance


def _get_or_create_scorecard() -> ScorecardDefaultConfig:
    """线程安全的懒加载获取 ScorecardDefaultConfig 实例"""
    global _scorecard_instance
    if _scorecard_instance is None:
        with _lock:
            if _scorecard_instance is None:
                _scorecard_instance = ScorecardDefaultConfig.from_env()
    return _scorecard_instance


def get_settings() -> Settings:
    """获取完整配置对象

    注意：大多数场景下建议使用 get_logging_config() / get_storage_config() 等具体方法，
         以减少不必要的依赖传递。

    返回:
        Settings 实例
    """
    return _get_or_create_settings()


def get_logging_config() -> LoggingConfig:
    """获取日志配置

    返回:
        LoggingConfig 实例
    """
    return _get_or_create_logging()


def get_storage_config() -> StorageConfig:
    """获取存储配置

    返回:
        StorageConfig 实例
    """
    return _get_or_create_storage()


def get_scorecard_config() -> ScorecardDefaultConfig:
    """获取评分卡配置

    返回:
        ScorecardDefaultConfig 实例
    """
    return _get_or_create_scorecard()


def reload_settings() -> Settings:
    """热重载所有配置

    使用场景：
      - 环境变量在运行时发生变化（如多租户切换）
      - 单元测试中需要隔离配置
      - 动态配置中心回调

    注意：重载后所有通过 get_xxx() 获取的配置都会更新。

    返回:
        新的 Settings 实例
    """
    global _settings_instance, _logging_instance, _storage_instance, _scorecard_instance
    with _lock:
        _settings_instance = Settings()
        _logging_instance = _settings_instance.logging
        _storage_instance = _settings_instance.storage
        _scorecard_instance = _settings_instance.scorecard
    return _settings_instance


def reload_logging_config() -> LoggingConfig:
    """热重载日志配置"""
    global _logging_instance
    with _lock:
        _logging_instance = LoggingConfig.from_env()
        # 同步更新 Settings 实例（如果存在）
        if _settings_instance:
            _settings_instance.logging = _logging_instance
    return _logging_instance


def reload_storage_config() -> StorageConfig:
    """热重载存储配置"""
    global _storage_instance
    with _lock:
        _storage_instance = StorageConfig.from_env()
        if _settings_instance:
            _settings_instance.storage = _storage_instance
    return _storage_instance


def reload_scorecard_config() -> ScorecardDefaultConfig:
    """热重载评分卡配置"""
    global _scorecard_instance
    with _lock:
        _scorecard_instance = ScorecardDefaultConfig.from_env()
        if _settings_instance:
            _settings_instance.scorecard = _scorecard_instance
    return _scorecard_instance


def reload_all_configs() -> None:
    """热重载所有配置

    一次性重新加载所有配置模块。
    """
    with _lock:
        global _settings_instance, _logging_instance, _storage_instance, _scorecard_instance
        _logging_instance = LoggingConfig.from_env()
        _storage_instance = StorageConfig.from_env()
        _scorecard_instance = ScorecardDefaultConfig.from_env()

        _settings_instance = Settings(
            logging=_logging_instance,
            storage=_storage_instance,
            scorecard=_scorecard_instance
        )


__all__ = [
    "get_settings",
    "get_logging_config",
    "get_storage_config",
    "get_scorecard_config",
    "reload_settings",
    "reload_logging_config",
    "reload_storage_config",
    "reload_scorecard_config",
    "reload_all_configs",
]