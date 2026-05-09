# Datamind/datamind/cli/commands/config.py

"""配置管理命令行命令

提供系统配置的查看、验证和重载功能，方便运维人员管理配置。

功能特性：
  - 查看当前配置（支持 table/json/yaml 格式）
  - 获取单个配置项
  - 验证配置有效性（检查日志配置等）
  - 显示 DATAMIND_ 开头的环境变量
  - 配置热重载（开发中）

命令列表：
  - config show: 显示当前配置
  - config get: 获取单个配置项
  - config validate: 验证配置有效性
  - config env: 显示环境变量
  - config reload: 重载配置（热更新）

使用示例：
  # 显示所有配置（表格格式）
  datamind config show

  # 显示配置（JSON格式）
  datamind config show --format json

  # 获取单个配置项
  datamind config get app_name

  # 验证配置
  datamind config validate

  # 查看环境变量
  datamind config env

  # 重载配置
  datamind config reload --force
"""

import click
import os
import json
import yaml

from datamind.cli.utils.printer import print_table, print_success, print_error
from datamind.config import settings
from datamind.config import LoggingConfig


@click.group(name='config')
def config():
    """配置管理命令"""
    pass


@config.command(name='show')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), default='table')
def show_config(format):
    """显示当前配置"""
    try:
        config_dict = {
            'app': {
                'name': settings.app.app_name,
                'version': settings.app.version,
                'env': settings.app.env,
                'debug': settings.app.debug
            },
            'api': {
                'host': settings.api.host,
                'port': settings.api.port,
                'prefix': settings.api.prefix
            },
            'database': {
                'url': settings.database.url.split('@')[-1] if '@' in settings.database.url else settings.database.url,
                'pool_size': settings.database.pool_size,
                'max_overflow': settings.database.max_overflow
            },
            'logging': {
                'level': settings.logging.level.name if hasattr(settings.logging.level, 'name') else str(
                    settings.logging.level),
                'format': settings.logging.format.value,
                'log_dir': settings.logging.log_dir
            },
            'security': {
                'api_key_enabled': settings.auth.api_key_enabled,
                'rate_limit_enabled': settings.security.rate_limit_enabled
            },
            'model': {
                'storage_path': settings.model.models_path,
                'inference_timeout': settings.inference.timeout
            }
        }

        if format == 'json':
            click.echo(json.dumps(config_dict, indent=2, ensure_ascii=False))
        elif format == 'yaml':
            click.echo(yaml.dump(config_dict, allow_unicode=True))
        else:
            for section, values in config_dict.items():
                click.echo(f"\n[{section}]")
                for key, value in values.items():
                    click.echo(f"  {key}: {value}")

    except Exception as e:
        print_error(f"获取配置失败: {e}")


@config.command(name='get')
@click.argument('key')
def get_config(key):
    """获取单个配置项"""
    try:
        # 尝试获取配置项
        value = getattr(settings, key, None)
        if value is None:
            print_error(f"配置项不存在: {key}")
            return

        click.echo(f"{key}: {value}")

    except Exception as e:
        print_error(f"获取配置失败: {e}")


@config.command(name='validate')
def validate_config():
    """验证配置有效性"""
    try:
        # 验证日志配置
        log_config = LoggingConfig()
        # 注意：LoggingConfig 是 Pydantic 模型，会自动验证
        # 这里只做简单验证

        click.echo("\n验证日志配置...")
        if log_config.sampling_rate < 0 or log_config.sampling_rate > 1:
            click.echo(f"  ⚠️ 采样率 {log_config.sampling_rate} 不在 0-1 范围内")

        if log_config.retention_days < 1:
            click.echo(f"  ⚠️ 日志保留天数 {log_config.retention_days} 过小")

        click.echo(f"\n环境: {settings.app.env}")
        click.echo(f"调试模式: {'开启' if settings.app.debug else '关闭'}")
        print_success("配置验证通过")

    except Exception as e:
        print_error(f"验证失败: {e}")


@config.command(name='env')
def show_env():
    """显示环境变量"""
    env_vars = {k: v for k, v in os.environ.items() if k.startswith('DATAMIND_')}

    if not env_vars:
        click.echo("未找到 DATAMIND_ 开头的环境变量")
        return

    headers = ['环境变量', '值']
    rows = []
    for key, value in env_vars.items():
        # 隐藏敏感信息
        if any(s in key.lower() for s in ['password', 'secret', 'key']):
            value = '******'
        rows.append([key, value])

    print_table(headers, rows)


@config.command(name='reload')
@click.option('--force', '-f', is_flag=True, help='强制重载')
def reload_config(force):
    """重载配置"""
    try:
        if force:
            click.confirm('确定要重载配置吗？', abort=True)

        # TODO: 实现配置热重载
        click.echo("配置重载功能开发中...")

    except Exception as e:
        print_error(f"重载失败: {e}")