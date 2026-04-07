# datamind/config/__init__.py

"""Datamind 配置模块

提供统一的配置管理入口，支持懒加载、热重载和线程安全的配置访问。

核心功能：
  - get_settings: 获取完整配置对象
  - get_logging_config: 获取日志配置
  - get_storage_config: 获取存储配置
  - get_scorecard_config: 获取评分卡配置
  - reload_settings: 热重载所有配置
  - reload_logging_config: 热重载日志配置
  - reload_storage_config: 热重载存储配置
  - reload_scorecard_config: 热重载评分卡配置
  - reload_all_configs: 热重载所有配置

特性：
  - 懒加载：配置在首次访问时初始化，不阻塞启动
  - 线程安全：使用双重检查锁保证并发安全
  - 热重载：支持运行时重新加载配置（用于多租户/动态环境）
  - 统一入口：所有配置通过 get_xxx() 获取
  - 独立环境变量：每个配置模块使用独立的环境变量前缀
  - 测试友好：支持在单元测试中替换配置实现
"""

from dotenv import load_dotenv

from datamind import PROJECT_ROOT


def _load_env_file() -> None:
    """加载 .env 文件

    加载顺序：
        - 优先从项目根目录加载
        - 如果找不到，尝试从当前工作目录加载
        - 不覆盖已存在的系统环境变量（系统变量优先级更高）
    """
    env_file = PROJECT_ROOT / '.env'

    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)


_load_env_file()


from .manager import (
    get_settings,
    get_logging_config,
    get_storage_config,
    get_scorecard_config,
    reload_settings,
    reload_logging_config,
    reload_storage_config,
    reload_scorecard_config,
    reload_all_configs,
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