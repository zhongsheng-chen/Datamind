import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / '.datamind'
CONFIG_FILE = CONFIG_DIR / 'config.json'


def init_config():
    """初始化配置目录"""
    CONFIG_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        default_config = {
            'api_url': 'http://localhost:8000',
            'bento_scoring_url': 'http://localhost:3000',
            'bento_fraud_url': 'http://localhost:3001',
            'log_path': './logs',
            'timeout': 30,
            'format': 'table'
        }
        save_config(default_config)


def get_config() -> dict:
    """获取配置"""
    if not CONFIG_FILE.exists():
        init_config()

    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_config(config: dict):
    """保存配置"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_api_url() -> str:
    """获取API URL"""
    config = get_config()
    return config.get('api_url', 'http://localhost:8000')


def get_bento_url(task_type: str) -> str:
    """获取BentoML服务URL"""
    config = get_config()
    if task_type == 'scoring':
        return config.get('bento_scoring_url', 'http://localhost:3000')
    else:
        return config.get('bento_fraud_url', 'http://localhost:3001')


def get_log_path() -> str:
    """获取日志路径"""
    config = get_config()
    return config.get('log_path', './logs')


def get_headers() -> dict:
    """获取请求头"""
    config = get_config()
    headers = {
        'Content-Type': 'application/json'
    }
    # 如果有API密钥
    api_key = config.get('api_key')
    if api_key:
        headers['X-API-Key'] = api_key
    return headers