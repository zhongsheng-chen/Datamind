#!/usr/bin/env python
"""
Datamind 命令行工具入口

使用方式：
    datamind model register --file model.pkl --name "信用模型"
    datamind audit list --days 7
    datamind log tail --level ERROR
"""

import click
from rich.console import Console
from rich.traceback import install
from cli.commands import model, audit, log, config, health, version

# 安装rich traceback
install()

console = Console()

@click.group()
@click.option('--config', '-c', help='配置文件路径')
@click.option('--env', '-e', default='production', help='环境名称')
@click.option('--debug', is_flag=True, help='调试模式')
@click.version_option(version='1.0.0')
@click.pass_context
def cli(ctx, config, env, debug):
    """Datamind 模型部署平台命令行工具"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['env'] = env
    ctx.obj['debug'] = debug

# 注册命令
cli.add_command(model.model)
cli.add_command(audit.audit)
cli.add_command(log.log)
cli.add_command(config.config)
cli.add_command(health.health)
cli.add_command(version.version)

if __name__ == '__main__':
    cli()