# datamind/cli/commands/log.py
import click
from datetime import datetime, timedelta
from pathlib import Path
import json
import gzip
import shutil
import os
import re

from cli.utils.printer import (
    print_table, print_json, print_success,
    print_error, print_warning, print_header
)
from config.settings import settings


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
    log_paths = {
        'access': Path(settings.LOG_PATH) / 'access.log',
        'audit': Path(settings.LOG_PATH) / 'audit.log',
        'performance': Path(settings.LOG_PATH) / 'performance.log',
        'error': Path(settings.LOG_PATH) / 'Datamind.error.log',
        'all': Path(settings.LOG_PATH)
    }

    if log_type == 'all':
        log_dir = log_paths['all']
        if not log_dir.exists():
            print_error(f"日志目录不存在: {log_dir}")
            return

        # 显示所有日志文件大小
        click.echo(f"\n日志目录: {log_dir}")
        click.echo("-" * 50)

        for log_file in log_dir.glob("*.log*"):
            size = log_file.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            modified = datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            click.echo(f"{log_file.name:<30} {size_str:>10} {modified:>20}")
        return

    log_file = log_paths.get(log_type)
    if not log_file or not log_file.exists():
        print_error(f"日志文件不存在: {log_file}")
        return

    try:
        if follow:
            click.echo(f"跟踪日志文件: {log_file} (按 Ctrl+C 退出)")
            with open(log_file, 'r') as f:
                # 跳到最后
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        if grep and grep not in line:
                            continue
                        click.echo(line.rstrip())
                    else:
                        import time
                        time.sleep(0.1)
        else:
            # 读取最后几行
            with open(log_file, 'r') as f:
                lines = f.readlines()
                start = max(0, len(lines) - lines)
                for line in lines[start:]:
                    if grep and grep not in line:
                        continue
                    click.echo(line.rstrip())

    except KeyboardInterrupt:
        click.echo("\n退出日志跟踪")
    except Exception as e:
        print_error(f"读取日志失败: {e}")


@log.command(name='search')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error']))
@click.option('--keyword', '-k', required=True, help='搜索关键词')
@click.option('--since', '-s', help='起始时间 (例如: "2024-01-01" 或 "7d" 表示7天前)')
@click.option('--until', '-u', help='结束时间')
@click.option('--limit', '-l', default=100, help='最大返回条数')
@click.option('--format', '-f', 'output_format', type=click.Choice(['text', 'json']), default='text')
def search_logs(log_type, keyword, since, until, limit, output_format):
    """搜索日志"""
    log_file = Path(settings.LOG_PATH) / f"{log_type}.log"

    if not log_file.exists():
        print_error(f"日志文件不存在: {log_file}")
        return

    try:
        # 解析时间范围
        start_time = None
        end_time = None

        if since:
            if since.endswith('d'):
                days = int(since[:-1])
                start_time = datetime.now() - timedelta(days=days)
            else:
                start_time = datetime.strptime(since, '%Y-%m-%d')

        if until:
            end_time = datetime.strptime(until, '%Y-%m-%d')

        results = []
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if keyword not in line:
                    continue

                # 时间过滤
                if start_time or end_time:
                    # 尝试从日志行中提取时间 (格式可能不同)
                    time_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                    if time_match:
                        log_time = datetime.strptime(time_match.group(), '%Y-%m-%d %H:%M:%S')
                        if start_time and log_time < start_time:
                            continue
                        if end_time and log_time > end_time:
                            continue

                results.append({
                    'line': line_num,
                    'content': line.rstrip()
                })

                if len(results) >= limit:
                    break

        if not results:
            print_warning(f"未找到包含 '{keyword}' 的日志")
            return

        if output_format == 'json':
            print_json(results)
        else:
            click.echo(f"\n找到 {len(results)} 条匹配记录:\n")
            for r in results:
                click.echo(f"{r['line']:6d} | {r['content']}")

    except Exception as e:
        print_error(f"搜索日志失败: {e}")


@log.command(name='export')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--since', '-s', help='起始时间 (例如: "2024-01-01" 或 "7d")')
@click.option('--until', '-u', help='结束时间')
@click.option('--compress', '-c', is_flag=True, help='压缩输出文件')
def export_logs(log_type, output, since, until, compress):
    """导出日志"""
    try:
        # 解析时间范围
        start_time = None
        end_time = None

        if since:
            if since.endswith('d'):
                days = int(since[:-1])
                start_time = datetime.now() - timedelta(days=days)
            else:
                start_time = datetime.strptime(since, '%Y-%m-%d')

        if until:
            end_time = datetime.strptime(until, '%Y-%m-%d')

        if log_type == 'all':
            log_files = list(Path(settings.LOG_PATH).glob("*.log*"))
        else:
            log_file = Path(settings.LOG_PATH) / f"{log_type}.log"
            if not log_file.exists():
                print_error(f"日志文件不存在: {log_file}")
                return
            log_files = [log_file]

        output_path = Path(output)
        if compress:
            output_path = output_path.with_suffix('.gz')

        with click.progressbar(log_files, label='导出日志') as bar:
            if compress:
                with gzip.open(output_path, 'wt', encoding='utf-8') as out_f:
                    for log_file in bar:
                        out_f.write(f"\n{'=' * 60}\n")
                        out_f.write(f"文件: {log_file.name}\n")
                        out_f.write(f"{'=' * 60}\n\n")

                        with open(log_file, 'r') as in_f:
                            for line in in_f:
                                if start_time or end_time:
                                    time_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                                    if time_match:
                                        log_time = datetime.strptime(time_match.group(), '%Y-%m-%d %H:%M:%S')
                                        if start_time and log_time < start_time:
                                            continue
                                        if end_time and log_time > end_time:
                                            continue
                                out_f.write(line)
            else:
                with open(output_path, 'w', encoding='utf-8') as out_f:
                    for log_file in bar:
                        out_f.write(f"\n{'=' * 60}\n")
                        out_f.write(f"文件: {log_file.name}\n")
                        out_f.write(f"{'=' * 60}\n\n")

                        with open(log_file, 'r') as in_f:
                            for line in in_f:
                                if start_time or end_time:
                                    time_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                                    if time_match:
                                        log_time = datetime.strptime(time_match.group(), '%Y-%m-%d %H:%M:%S')
                                        if start_time and log_time < start_time:
                                            continue
                                        if end_time and log_time > end_time:
                                            continue
                                out_f.write(line)

        size = output_path.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
        print_success(f"日志已导出到 {output_path} ({size_str})")

    except Exception as e:
        print_error(f"导出日志失败: {e}")


@log.command(name='rotate')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--keep', '-k', default=30, help='保留的备份数量')
def rotate_logs(log_type, keep):
    """手动轮转日志"""
    try:
        if log_type == 'all':
            log_files = list(Path(settings.LOG_PATH).glob("*.log"))
        else:
            log_file = Path(settings.LOG_PATH) / f"{log_type}.log"
            if not log_file.exists():
                print_error(f"日志文件不存在: {log_file}")
                return
            log_files = [log_file]

        for log_file in log_files:
            if log_file.stat().st_size == 0:
                continue

            # 生成轮转文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            rotated = log_file.with_suffix(f'.log.{timestamp}')

            # 重命名当前日志
            shutil.move(str(log_file), str(rotated))

            # 创建新的空日志文件
            log_file.touch()

            click.echo(f"轮转: {log_file.name} -> {rotated.name}")

            # 清理旧备份
            backups = sorted(log_file.parent.glob(f"{log_file.stem}.log.*"))
            if len(backups) > keep:
                for old in backups[:-keep]:
                    old.unlink()
                    click.echo(f"删除旧备份: {old.name}")

        print_success("日志轮转完成")

    except Exception as e:
        print_error(f"日志轮转失败: {e}")


@log.command(name='stats')
@click.argument('log-type', type=click.Choice(['access', 'audit', 'performance', 'error', 'all']))
@click.option('--days', '-d', default=7, help='统计最近几天的日志')
def log_stats(log_type, days):
    """查看日志统计信息"""
    try:
        from collections import Counter, defaultdict

        start_time = datetime.now() - timedelta(days=days)

        if log_type == 'all':
            log_files = list(Path(settings.LOG_PATH).glob("*.log*"))
        else:
            log_file = Path(settings.LOG_PATH) / f"{log_type}.log"
            if not log_file.exists():
                print_error(f"日志文件不存在: {log_file}")
                return
            log_files = [log_file]

        total_lines = 0
        daily_counts = defaultdict(int)
        level_counts = Counter()
        endpoint_counts = Counter()
        status_counts = Counter()
        user_counts = Counter()

        for log_file in log_files:
            with open(log_file, 'r') as f:
                for line in f:
                    total_lines += 1

                    # 提取日期
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        date = date_match.group(1)
                        daily_counts[date] += 1

                    # 提取日志级别
                    if 'ERROR' in line or 'ERROR' in line.upper():
                        level_counts['ERROR'] += 1
                    elif 'WARNING' in line or 'WARN' in line.upper():
                        level_counts['WARNING'] += 1
                    elif 'INFO' in line.upper():
                        level_counts['INFO'] += 1
                    elif 'DEBUG' in line.upper():
                        level_counts['DEBUG'] += 1

                    # 如果是access日志，提取更多信息
                    if 'access' in str(log_file):
                        # 提取HTTP状态码
                        status_match = re.search(r'status[=:](\d{3})', line)
                        if status_match:
                            status = status_match.group(1)
                            status_counts[status] += 1

                        # 提取端点
                        endpoint_match = re.search(r'path[=:]["\']?([^"\'\s]+)', line)
                        if endpoint_match:
                            endpoint = endpoint_match.group(1)
                            endpoint_counts[endpoint] += 1

                        # 提取用户
                        user_match = re.search(r'user[=:]["\']?([^"\'\s]+)', line)
                        if user_match:
                            user = user_match.group(1)
                            user_counts[user] += 1

        # 打印统计信息
        print_header(f"日志统计 ({log_type})")

        info_table = [
            ['统计项', '数值'],
            ['-' * 20, '-' * 20],
            ['总行数', str(total_lines)],
            ['日志文件数', str(len(log_files))],
            ['时间范围', f"最近 {days} 天"],
        ]
        print_table(['统计项', '数值'], info_table[1:], header=info_table[0])

        if level_counts:
            click.echo("\n日志级别分布:")
            for level, count in level_counts.most_common():
                percentage = (count / total_lines) * 100 if total_lines else 0
                click.echo(f"  {level}: {count} ({percentage:.1f}%)")

        if status_counts:
            click.echo("\nHTTP状态码分布:")
            for status, count in status_counts.most_common():
                percentage = (count / total_lines) * 100 if total_lines else 0
                click.echo(f"  {status}: {count} ({percentage:.1f}%)")

        if endpoint_counts:
            click.echo("\n最常访问的端点:")
            for endpoint, count in endpoint_counts.most_common(10):
                click.echo(f"  {endpoint}: {count}")

        if user_counts:
            click.echo("\n最活跃的用户:")
            for user, count in user_counts.most_common(5):
                click.echo(f"  {user}: {count}")

        if daily_counts:
            click.echo("\n每日日志量:")
            for date in sorted(daily_counts.keys())[-7:]:  # 最近7天
                count = daily_counts[date]
                bar = '█' * min(int(count / max(daily_counts.values()) * 30), 30)
                click.echo(f"  {date}: {bar} {count}")

    except Exception as e:
        print_error(f"统计日志失败: {e}")


@log.command(name='clean')
@click.option('--days', '-d', default=30, help='删除多少天前的日志')
@click.option('--dry-run', is_flag=True, help='只显示要删除的文件，不实际删除')
def clean_logs(days, dry_run):
    """清理旧日志文件"""
    try:
        cutoff_time = datetime.now() - timedelta(days=days)
        log_dir = Path(settings.LOG_PATH)

        if not log_dir.exists():
            print_error(f"日志目录不存在: {log_dir}")
            return

        to_delete = []
        total_size = 0

        for log_file in log_dir.glob("*.log*"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff_time:
                size = log_file.stat().st_size
                to_delete.append((log_file, size))
                total_size += size

        if not to_delete:
            print_success(f"没有找到 {days} 天前的日志文件")
            return

        # 显示要删除的文件
        click.echo(f"\n将删除以下 {len(to_delete)} 个文件:")
        for log_file, size in sorted(to_delete):
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            click.echo(f"  {log_file.name:<40} {size_str:>10} {mtime}")

        total_size_str = f"{total_size / 1024 / 1024:.1f} MB"
        click.echo(f"\n总计释放空间: {total_size_str}")

        if dry_run:
            print_warning("这是试运行，未实际删除文件")
            return

        if click.confirm(f"\n确定要删除这些文件吗？"):
            for log_file, _ in to_delete:
                log_file.unlink()
                click.echo(f"已删除: {log_file.name}")
            print_success(f"清理完成，释放 {total_size_str} 空间")
        else:
            print_warning("操作已取消")

    except Exception as e:
        print_error(f"清理日志失败: {e}")


@log.command(name='config')
def show_log_config():
    """显示日志配置"""
    try:
        from config.logging_config import LoggingConfig

        log_config = LoggingConfig.load()

        print_header("日志配置")

        config_items = [
            ['日志级别', log_config.level.value],
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