import click
import subprocess
from pathlib import Path
from cli.utils.config import get_log_path


@click.group(name='log')
def log():
    """日志管理"""
    pass


@log.command(name='tail')
@click.option('--file', '-f', type=click.Choice(['app', 'error', 'access', 'audit', 'performance']),
              default='app', help='日志文件')
@click.option('--lines', '-n', type=int, default=50, help='显示行数')
@click.option('--level', '-l', help='过滤级别')
@click.option('--follow', '-F', is_flag=True, help='持续跟踪')
def tail_logs(file, lines, level, follow):
    """实时查看日志"""
    log_files = {
        'app': 'Datamind.log',
        'error': 'Datamind.error.log',
        'access': 'access.log',
        'audit': 'audit.log',
        'performance': 'performance.log'
    }

    log_path = Path(get_log_path()) / log_files[file]

    if not log_path.exists():
        click.echo(f"日志文件不存在: {log_path}")
        return

    cmd = ['tail']
    if follow:
        cmd.append('-f')
    cmd.extend(['-n', str(lines), str(log_path)])

    if level:
        # 使用grep过滤级别
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['grep', '--color=always', level], stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        output = p2.communicate()[0]
        click.echo(output.decode())
    else:
        subprocess.run(cmd)


@log.command(name='search')
@click.argument('pattern')
@click.option('--file', '-f', type=click.Choice(['app', 'error', 'access', 'audit', 'performance']),
              multiple=True, help='日志文件')
@click.option('--days', '-d', type=int, default=1, help='搜索天数')
def search_logs(pattern, file, days):
    """搜索日志"""
    from datetime import datetime, timedelta

    log_files = {
        'app': 'Datamind.log',
        'error': 'Datamind.error.log',
        'access': 'access.log',
        'audit': 'audit.log',
        'performance': 'performance.log'
    }

    log_path = Path(get_log_path())

    # 确定要搜索的文件
    files_to_search = file if file else ['app', 'error', 'access', 'audit', 'performance']

    for f in files_to_search:
        log_file = log_path / log_files[f]
        if not log_file.exists():
            continue

        click.echo(f"\n[bold]搜索 {log_files[f]}:[/bold]")

        # 使用grep搜索
        cmd = ['grep', '--color=always', '-n', pattern, str(log_file)]
        subprocess.run(cmd)


@log.command(name='rotate')
@click.option('--force', '-f', is_flag=True, help='强制轮转')
def rotate_logs(force):
    """手动触发日志轮转"""
    import logging
    from core.log_manager import log_manager

    if not force:
        click.confirm('确定要手动触发日志轮转吗？', abort=True)

    try:
        # 关闭所有日志处理器
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

        # 重新初始化日志系统
        from config.logging_config import LoggingConfig
        log_manager.initialize(LoggingConfig())

        click.echo("日志轮转完成")

    except Exception as e:
        click.echo(f"轮转失败: {str(e)}")


@log.command(name='clean')
@click.option('--days', '-d', type=int, help='保留天数，覆盖配置文件')
@click.option('--dry-run', is_flag=True, help='试运行，只显示要删除的文件')
def clean_logs(days, dry_run):
    """清理旧日志文件"""
    from pathlib import Path
    import time
    from datetime import datetime, timedelta

    log_path = Path(get_log_path())
    retention_days = days or 90  # 默认90天
    cutoff_time = time.time() - (retention_days * 24 * 3600)

    click.echo(f"清理 {retention_days} 天前的日志文件...")

    deleted_count = 0
    for log_file in log_path.glob('*.log*'):
        if log_file.is_file() and log_file.stat().st_mtime < cutoff_time:
            if dry_run:
                click.echo(f"将删除: {log_file}")
            else:
                log_file.unlink()
                click.echo(f"已删除: {log_file}")
            deleted_count += 1

    click.echo(f"共清理 {deleted_count} 个文件")