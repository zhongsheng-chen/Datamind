# Datamind/datamind/cli/utils/config.py

"""CLI 配置管理器

提供命令行工具的配置管理功能，支持配置文件、环境变量和默认配置。

功能特性：
  - 多级配置加载（默认配置 → 用户配置 → 环境变量）
  - 配置文件自动发现（支持多种路径）
  - 点号分隔的配置键访问（如 'api.host'）
  - 深度合并配置字典
  - 环境变量覆盖支持
  - 配置保存功能

配置加载优先级（从低到高）：
  - 默认配置
  - 用户配置文件
  - 环境变量

配置文件查找路径（按优先级）：
  - 命令行指定的配置文件
  - 当前目录下的 .datamind-cli.json
  - ~/.config/datamind/cli.json
  - 用户目录下的 .datamind-cli.json

配置结构：
  {
    "api": {
      "host": "localhost",      // API 服务主机
      "port": 8000,             // API 服务端口
      "timeout": 30             // 请求超时时间（秒）
    },
    "format": "table",          // 输出格式（table/json）
    "color": true,              // 是否启用彩色输出
    "history_size": 100         // 历史记录大小
  }

环境变量：
  - DATAMIND_API_HOST: 覆盖 api.host
  - DATAMIND_API_PORT: 覆盖 api.port
  - DATAMIND_API_TIMEOUT: 覆盖 api.timeout

使用示例：
  # 创建配置管理器
  config = CLIConfig()

  # 获取配置项
  host = config.get('api.host', 'localhost')
  port = config.get('api.port', 8000)

  # 设置配置项
  config.set('api.timeout', 60)
  config.save()  # 保存到配置文件

  # 指定配置文件路径
  config = CLIConfig(config_file='/path/to/config.json')
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


class CLIConfig:
    """CLI配置管理器"""

    DEFAULT_CONFIG = {
        'api': {
            'host': 'localhost',
            'port': 8000,
            'timeout': 30
        },
        'format': 'table',
        'color': True,
        'history_size': 100
    }

    def __init__(self, config_file: Optional[str] = None, env: str = 'production', debug: bool = False):
        """
        初始化配置管理器

        参数:
            config_file: 配置文件路径，为 None 时自动查找
            env: 运行环境（development/testing/staging/production）
            debug: 是否开启调试模式
        """
        self.env = env
        self.debug = debug
        self.config_file = self._find_config_file(config_file)
        self.config = self._load_config()

    def _find_config_file(self, config_file: Optional[str] = None) -> Path:
        """查找配置文件

        按优先级顺序查找配置文件：
          1. 命令行指定的路径
          2. 当前目录下的 .datamind-cli.json
          3. ~/.config/datamind/cli.json
          4. 用户目录下的 .datamind-cli.json

        参数:
            config_file: 指定的配置文件路径

        返回:
            Path 对象，如果文件不存在则返回默认路径
        """
        if config_file:
            return Path(config_file)

        # 按优先级查找
        locations = [
            Path.cwd() / '.datamind-cli.json',
            Path.home() / '.config' / 'datamind' / 'cli.json',
            Path.home() / '.datamind-cli.json',
        ]

        for loc in locations:
            if loc.exists():
                return loc

        return Path.cwd() / '.datamind-cli.json'

    def _load_config(self) -> Dict[str, Any]:
        """加载配置

        加载顺序：
          1. 默认配置
          2. 用户配置文件（如果存在）
          3. 环境变量覆盖

        返回:
            合并后的配置字典
        """
        config = self.DEFAULT_CONFIG.copy()

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                    self._deep_update(config, user_config)
            except Exception as e:
                if self.debug:
                    print(f"加载配置文件失败: {e}")

        # 环境变量覆盖
        self._apply_env_overrides(config)

        return config

    def _deep_update(self, target: Dict, source: Dict):
        """深度更新字典

        递归合并两个字典，嵌套字典会深度合并而不是覆盖。

        参数:
            target: 目标字典（会被修改）
            source: 源字典
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def _apply_env_overrides(self, config: Dict):
        """应用环境变量覆盖

        使用环境变量覆盖配置项：
          - DATAMIND_API_HOST → config['api']['host']
          - DATAMIND_API_PORT → config['api']['port']（自动转换为整数）
          - DATAMIND_API_TIMEOUT → config['api']['timeout']（自动转换为整数）

        参数:
            config: 配置字典（会被修改）
        """
        # API主机
        if os.getenv('DATAMIND_API_HOST'):
            config['api']['host'] = os.getenv('DATAMIND_API_HOST')

        # API端口
        if os.getenv('DATAMIND_API_PORT'):
            try:
                config['api']['port'] = int(os.getenv('DATAMIND_API_PORT'))
            except ValueError:
                if self.debug:
                    print(f"警告: 环境变量 DATAMIND_API_PORT 值无效: {os.getenv('DATAMIND_API_PORT')}")

        # 超时时间
        if os.getenv('DATAMIND_API_TIMEOUT'):
            try:
                config['api']['timeout'] = int(os.getenv('DATAMIND_API_TIMEOUT'))
            except ValueError:
                if self.debug:
                    print(f"警告: 环境变量 DATAMIND_API_TIMEOUT 值无效: {os.getenv('DATAMIND_API_TIMEOUT')}")

    def save(self):
        """保存配置到文件

        创建配置目录（如果不存在），将当前配置写入 JSON 文件。
        """
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        参数:
            key: 配置键，支持点号分隔，如 'api.host'
            default: 默认值，当键不存在时返回

        返回:
            配置值，如果键不存在则返回 default

        示例:
            host = config.get('api.host', 'localhost')
            port = config.get('api.port', 8000)
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def set(self, key: str, value: Any):
        """
        设置配置项

        参数:
            key: 配置键，支持点号分隔，如 'api.timeout'
            value: 配置值

        示例:
            config.set('api.timeout', 60)
            config.set('format', 'json')
        """
        keys = key.split('.')
        target = self.config

        # 遍历到倒数第二级，创建不存在的中间字典
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        # 设置最终值
        target[keys[-1]] = value