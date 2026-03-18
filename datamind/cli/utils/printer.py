# Datamind/datamind/cli/utils/printer.py
import click
import json
from typing import List, Any


def print_header(text: str):
    """打印标题"""
    click.echo(click.style(f"\n{text}", fg='bright_blue', bold=True))


def print_success(text: str):
    """打印成功信息"""
    click.echo(click.style(f"✅ {text}", fg='green'))


def print_error(text: str):
    """打印错误信息"""
    click.echo(click.style(f"❌ {text}", fg='red'), err=True)


def print_warning(text: str):
    """打印警告信息"""
    click.echo(click.style(f"⚠️  {text}", fg='yellow'))


def print_info(text: str):
    """打印信息"""
    click.echo(click.style(f"ℹ️  {text}", fg='cyan'))


def print_table(headers: List[str], rows: List[List[Any]], header: List[str] = None):
    """
    打印表格

    参数:
        headers: 表头
        rows: 数据行
        header: 可选的额外表头
    """
    if header:
        click.echo("\n" + header[0] + " " + header[1])

    # 计算每列最大宽度
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # 打印表头
    header_line = ""
    for i, header in enumerate(headers):
        header_line += header.ljust(col_widths[i] + 2)
    click.echo(click.style(header_line, bold=True))

    # 打印分隔线
    separator = "-" * (sum(col_widths) + len(col_widths) * 2)
    click.echo(separator)

    # 打印数据行
    for row in rows:
        line = ""
        for i, cell in enumerate(row):
            line += str(cell).ljust(col_widths[i] + 2)
        click.echo(line)


def print_json(data: Any):
    """打印JSON格式"""
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def print_progress(current: int, total: int, prefix: str = '', suffix: str = ''):
    """
    打印进度条

    参数:
        current: 当前进度
        total: 总进度
        prefix: 前缀
        suffix: 后缀
    """
    bar_length = 50
    filled_length = int(bar_length * current / total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    percent = f"{100 * current / total:.1f}"
    click.echo(f"\r{prefix} |{bar}| {percent}% {suffix}", nl=False)

    if current == total:
        click.echo()