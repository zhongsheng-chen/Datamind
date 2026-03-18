# datamind/cli/commands/config.py
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
                'name': settings.APP_NAME,
                'version': settings.VERSION,
                'env': settings.ENV,
                'debug': settings.DEBUG
            },
            'api': {
                'host': settings.API_HOST,
                'port': settings.API_PORT,
                'prefix': settings.API_PREFIX
            },
            'database': {
                'url': settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL,
                'pool_size': settings.DB_POOL_SIZE,
                'max_overflow': settings.DB_MAX_OVERFLOW
            },
            'logging': {
                'level': settings.LOG_LEVEL,
                'format': settings.LOG_FORMAT,
                'path': settings.LOG_PATH
            },
            'security': {
                'api_key_enabled': settings.API_KEY_ENABLED,
                'rate_limit_enabled': settings.RATE_LIMIT_ENABLED
            },
            'model': {
                'storage_path': settings.MODELS_PATH,
                'inference_timeout': settings.MODEL_INFERENCE_TIMEOUT
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
        value = getattr(settings, key.upper(), None)
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
        log_config = LoggingConfig.load()
        validation = log_config.validate_all()

        if validation['valid']:
            print_success("配置验证通过")
        else:
            print_error("配置验证失败:")
            for error in validation['errors']:
                click.echo(f"  ❌ {error}")

        if validation['warnings']:
            click.echo("\n警告:")
            for warning in validation['warnings']:
                click.echo(f"  ⚠️ {warning}")

        click.echo(f"\n环境: {settings.ENV}")
        click.echo(f"调试模式: {'开启' if settings.DEBUG else '关闭'}")

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