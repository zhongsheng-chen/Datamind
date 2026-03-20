# Datamind/datamind/cli/utils/printer.py

"""CLI 输出格式化工具

提供命令行界面的格式化输出功能，包括彩色输出、表格打印、JSON 格式化、进度条等。

功能特性：
  - 彩色输出：成功、错误、警告、信息等不同颜色
  - 表格打印：自动计算列宽，对齐输出
  - JSON 格式化：美化 JSON 输出
  - 进度条：显示任务进度
  - 标题打印：突出显示章节标题

输出颜色说明：
  - 成功（✅）：绿色
  - 错误（❌）：红色（输出到 stderr）
  - 警告（⚠️）：黄色
  - 信息（ℹ️）：青色
  - 标题：亮蓝色加粗

使用示例：
  # 打印成功信息
  print_success("模型注册成功")

  # 打印错误信息
  print_error("连接数据库失败")

  # 打印警告信息
  print_warning("配置项未设置，使用默认值")

  # 打印信息
  print_info("正在加载模型...")

  # 打印标题
  print_header("模型详情")

  # 打印表格
  headers = ['ID', '名称', '状态']
  rows = [
      ['1', '模型A', '活跃'],
      ['2', '模型B', '停用']
  ]
  print_table(headers, rows)

  # 打印 JSON
  print_json({"name": "test", "version": "1.0"})

  # 打印进度条
  for i in range(101):
      print_progress(i, 100, prefix="加载中", suffix="完成")
"""

import click
import json
from typing import List, Any


def print_header(text: str):
    """打印标题

    使用亮蓝色加粗样式突出显示章节标题。

    参数:
        text: 标题文本
    """
    click.echo(click.style(f"\n{text}", fg='bright_blue', bold=True))


def print_success(text: str):
    """打印成功信息

    使用绿色和 ✅ 图标表示操作成功。

    参数:
        text: 成功信息文本
    """
    click.echo(click.style(f"✅ {text}", fg='green'))


def print_error(text: str):
    """打印错误信息

    使用红色和 ❌ 图标表示操作失败，输出到 stderr。

    参数:
        text: 错误信息文本
    """
    click.echo(click.style(f"❌ {text}", fg='red'), err=True)


def print_warning(text: str):
    """打印警告信息

    使用黄色和 ⚠️ 图标表示需要注意的情况。

    参数:
        text: 警告信息文本
    """
    click.echo(click.style(f"⚠️  {text}", fg='yellow'))


def print_info(text: str):
    """打印信息

    使用青色和 ℹ️ 图标表示普通提示信息。

    参数:
        text: 信息文本
    """
    click.echo(click.style(f"ℹ️  {text}", fg='cyan'))


def print_table(headers: List[str], rows: List[List[Any]], header: List[str] = None):
    """
    打印表格

    自动计算每列的最大宽度，确保对齐显示。

    参数:
        headers: 表头列表
        rows: 数据行列表，每行是一个列表
        header: 可选的额外表头（已废弃，保留用于兼容）

    示例:
        >>> print_table(['ID', '名称'], [['1', '模型A'], ['2', '模型B']])
        ID    名称
        -----------
        1     模型A
        2     模型B
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
    for i, header_text in enumerate(headers):
        header_line += header_text.ljust(col_widths[i] + 2)
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
    """打印JSON格式

    将 Python 对象格式化为缩进的 JSON 字符串输出。

    参数:
        data: 要打印的数据，可以是字典、列表等可序列化对象

    示例:
        >>> print_json({"name": "test", "score": 95.5})
        {
          "name": "test",
          "score": 95.5
        }
    """
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def print_progress(current: int, total: int, prefix: str = '', suffix: str = ''):
    """
    打印进度条

    在终端显示一个动态更新的进度条，适合长时间操作。

    参数:
        current: 当前进度（0 到 total）
        total: 总进度
        prefix: 进度条前缀文本
        suffix: 进度条后缀文本

    示例:
        >>> for i in range(101):
        ...     print_progress(i, 100, prefix="加载中", suffix="完成")
        ...     time.sleep(0.05)
        加载中 |██████████████████████████████████████████████████| 100.0% 完成
    """
    bar_length = 50
    filled_length = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    percent = f"{100 * current / total:.1f}" if total > 0 else "0.0"
    click.echo(f"\r{prefix} |{bar}| {percent}% {suffix}", nl=False)

    if current == total:
        click.echo()