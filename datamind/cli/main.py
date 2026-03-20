#!/usr/bin/env python3
# Datamind/datamind/cli/main.py

"""Datamind 命令行工具主入口

提供 CLI 的主命令入口和全局选项，整合所有子命令。

功能特性：
  - 全局配置管理（配置文件、环境、调试模式）
  - 命令注册（模型、审计、配置、健康、版本、日志）
  - 全局错误处理（KeyboardInterrupt、异常捕获）
  - 调试模式支持（详细错误堆栈）

全局选项：
  - --config, -c: 指定配置文件路径
  - --env, -e: 运行环境（development/testing/production）
  - --debug/--no-debug: 启用/禁用调试模式
  - --version: 显示版本信息
  - --help: 显示帮助信息

命令列表：
  - model: 模型管理（注册、激活、停用、加载等）
  - audit: 审计日志（查询、导出）
  - config: 配置管理（查看、验证、重载）
  - health: 健康检查（API、数据库、Redis）
  - log: 日志管理（查看、搜索、导出、清理）
  - version: 版本信息

使用示例：
  # 查看帮助
  datamind --help

  # 指定配置文件运行
  datamind --config ~/.datamind.json model list

  # 开发环境运行
  datamind --env development model list

  # 调试模式
  datamind --debug model register ...

  # 查看版本
  datamind --version

错误处理：
  - KeyboardInterrupt: 打印取消信息并退出
  - 普通异常: 打印错误信息（调试模式显示堆栈）
  - 其他异常: 友好提示，返回非零退出码
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

    示例:
        datamind model list                    # 列出所有模型
        datamind model show MDL_xxx           # 查看模型详情
        datamind audit list --days 7          # 查看最近7天审计日志
        datamind health check                 # 检查服务健康状态
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
    """CLI入口函数

    处理全局异常，提供友好的错误提示。
    """
    try:
        cli(obj={})
    except KeyboardInterrupt:
        print_error("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        # 如果命令行中包含 --debug，显示完整堆栈
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        else:
            print_error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()