# Datamind/datamind/cli/commands/log.py

"""日志管理命令行命令

提供日志查看、搜索、导出、轮转、清理和统计等功能，方便运维人员管理日志。

功能特性：
  - 实时查看日志（tail）
  - 关键词搜索日志
  - 导出日志到文件（支持压缩）
  - 手动轮转日志
  - 清理旧日志文件
  - 日志统计分析
  - 显示日志配置

命令列表：
  - log tail: 查看实时日志（支持 follow 模式）
  - log search: 搜索日志内容
  - log export: 导出日志到文件
  - log rotate: 手动轮转日志
  - log clean: 清理旧日志文件
  - log stats: 查看日志统计信息
  - log config: 显示日志配置

日志类型：
  - access: 访问日志（HTTP 请求）
  - audit: 审计日志（操作记录）
  - performance: 性能日志（耗时统计）
  - error: 错误日志
  - all: 所有日志

使用示例：
  # 查看最近 50 行访问日志
  datamind log tail access --lines 50

  # 实时跟踪错误日志
  datamind log tail error --follow

  # 搜索包含特定关键词的审计日志
  datamind log search audit --keyword "MODEL_REGISTER" --since 7d

  # 导出最近 7 天的访问日志
  datamind log export access --output logs.json --since 7d

  # 手动轮转错误日志，保留 30 个备份
  datamind log rotate error --keep 30

  # 清理 30 天前的日志文件（试运行）
  datamind log clean --days 30 --dry-run

  # 查看最近 7 天的日志统计
  datamind log stats access --days 7

  # 显示当前日志配置
  datamind log config

统计信息包括：
  - 总行数、日志文件数
  - 日志级别分布（INFO/WARNING/ERROR）
  - HTTP 状态码分布（访问日志）
  - 最常访问的端点（访问日志）
  - 最活跃的用户（访问日志）
  - 每日日志量趋势

安全特性：
  - 试运行模式：清理前预览要删除的文件
  - 确认提示：删除操作需要确认
  - 路径检查：防止路径遍历攻击
"""

import click
from datetime import datetime, timedelta
from pathlib import Path
import gzip
import shutil
import re

from datamind.cli.utils.printer import (
    print_table, print_json, print_success,
    print_error, print_warning, print_header
)
from datamind.config import settings


@click.group(name='log')
def log():
    """日志管理命令"""
    pass


@log.command(name='tail')
@click.argument('log-type', type=click.Choice(['all', 'access', 'audit', 'performance', 'error']))
@click.option('--lines', '-n', default=50, help='显示行数')
@click.option('--follow', '-f', is_flag=True, help='持续跟踪输出')
@click.option('--grep', '-g', help='过滤关键词')
def tail_logs(log_type, lines, follow, grep):
    """查看实时日志"""
    # ... 代码保持不变 ...


@log.command(name='search')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error']))
@click.option('--keyword', '-k', required=True, help='搜索关键词')
@click.option('--since', '-s', help='起始时间 (例如: "2024-01-01" 或 "7d" 表示7天前)')
@click.option('--until', '-u', help='结束时间')
@click.option('--limit', '-l', default=100, help='最大返回条数')
@click.option('--format', '-f', 'output_format', type=click.Choice(['text', 'json']), default='text')
def search_logs(log_type, keyword, since, until, limit, output_format):
    """搜索日志"""
    # ... 代码保持不变 ...


@log.command(name='export')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--since', '-s', help='起始时间 (例如: "2024-01-01" 或 "7d")')
@click.option('--until', '-u', help='结束时间')
@click.option('--compress', '-c', is_flag=True, help='压缩输出文件')
def export_logs(log_type, output, since, until, compress):
    """导出日志"""
    # ... 代码保持不变 ...


@log.command(name='rotate')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--keep', '-k', default=30, help='保留的备份数量')
def rotate_logs(log_type, keep):
    """手动轮转日志"""
    # ... 代码保持不变 ...


@log.command(name='stats')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--days', '-d', default=7, help='统计最近几天的日志')
def log_stats(log_type, days):
    """查看日志统计信息"""
    # ... 代码保持不变 ...


@log.command(name='clean')
@click.option('--days', '-d', default=30, help='删除多少天前的日志')
@click.option('--dry-run', is_flag=True, help='只显示要删除的文件，不实际删除')
def clean_logs(days, dry_run):
    """清理旧日志文件"""
    # ... 代码保持不变 ...


@log.command(name='config')
def show_log_config():
    """显示日志配置"""
    try:
        from datamind.config import LoggingConfig

        log_config = LoggingConfig()

        print_header("日志配置")

        config_items = [
            ['日志级别', log_config.level.name if hasattr(log_config.level, 'name') else str(log_config.level)],
            ['日志格式', log_config.format.value],
            ['日志文件', log_config.file],
            ['错误日志', log_config.error_file or '无'],
            ['访问日志', log_config.access_log_file],
            ['审计日志', log_config.audit_log_file],
            ['性能日志', log_config.performance_log_file],
            ['最大文件大小', f"{log_config.max_bytes / 1024 / 1024:.0f} MB"],
            ['备份数量', str(log_config.backup_count)],
            ['保留天数', str(log_config.retention_days)],
            ['时区', log_config.timezone.value],
            ['时间精度', log_config.timestamp_precision.value],
            ['采样率', str(log_config.sampling_rate)],
            ['脱敏敏感信息', '是' if log_config.mask_sensitive else '否'],
        ]

        print_table(['配置项', '值'], config_items)

        if log_config.rotation_when:
            click.echo(f"\n日志轮转: 每 {log_config.rotation_interval} {log_config.rotation_when.value}")

    except Exception as e:
        print_error(f"获取日志配置失败: {e}")