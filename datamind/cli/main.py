#!/usr/bin/env python3
# Datamind/datamind/cli/main.py
"""
Datamind 命令行工具主入口
"""

import click
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from datamind.cli.commands import model, audit, config, health, version, log
from datamind.cli.utils.config import CLIConfig
from datamind.cli.utils.printer import print_error


@click.group()
@click.option('--config', '-c', help='配置文件路径')
@click.option('--env', '-e', default='production', help='环境名称 (development/testing/production)')
@click.option('--debug/--no-debug', default=False, help='启用调试模式')
@click.version_option(version='1.0.0', prog_name='datamind')
@click.pass_context
def cli(ctx, config, env, debug):
    """
    Datamind 模型部署平台命令行工具

    提供模型管理、审计日志、配置管理等功能
    """
    # 初始化配置
    ctx.ensure_object(dict)

    # 加载CLI配置
    cli_config = CLIConfig(config_file=config, env=env, debug=debug)
    ctx.obj['config'] = cli_config

    # 打印调试信息
    if debug:
        click.echo(f"调试模式已启用")
        click.echo(f"环境: {env}")
        click.echo(f"配置文件: {cli_config.config_file}")


# 注册命令
cli.add_command(model.model)
cli.add_command(audit.audit)
cli.add_command(config.config)
cli.add_command(health.health)
cli.add_command(version.version)
cli.add_command(log.log)


def main():
    """CLI入口函数"""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        print_error("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        else:
            print_error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()