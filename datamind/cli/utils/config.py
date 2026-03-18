# Datamind/datamind/cli/utils/config.py
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
        self.env = env
        self.debug = debug
        self.config_file = self._find_config_file(config_file)
        self.config = self._load_config()

    def _find_config_file(self, config_file: Optional[str] = None) -> Path:
        """查找配置文件"""
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
        """加载配置"""
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
        """深度更新字典"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def _apply_env_overrides(self, config: Dict):
        """应用环境变量覆盖"""
        # API主机
        if os.getenv('DATAMIND_API_HOST'):
            config['api']['host'] = os.getenv('DATAMIND_API_HOST')

        # API端口
        if os.getenv('DATAMIND_API_PORT'):
            try:
                config['api']['port'] = int(os.getenv('DATAMIND_API_PORT'))
            except:
                pass

        # 超时时间
        if os.getenv('DATAMIND_API_TIMEOUT'):
            try:
                config['api']['timeout'] = int(os.getenv('DATAMIND_API_TIMEOUT'))
            except:
                pass

    def save(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        参数:
            key: 配置键，支持点号分隔，如 'api.host'
            default: 默认值
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
            key: 配置键，支持点号分隔
            value: 配置值
        """
        keys = key.split('.')
        target = self.config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value