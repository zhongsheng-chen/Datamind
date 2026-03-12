import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Any, Optional

console = Console()


def print_json(data: Any, title: Optional[str] = None):
    """格式化输出JSON"""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)

    if title:
        console.print(Panel(syntax, title=title, border_style="green"))
    else:
        console.print(syntax)


def print_table(table: Table):
    """输出表格"""
    console.print(table)


def print_success(message: str):
    """输出成功信息"""
    console.print(f"✅ {message}", style="bold green")


def print_error(message: str):
    """输出错误信息"""
    console.print(f"❌ {message}", style="bold red")


def print_warning(message: str):
    """输出警告信息"""
    console.print(f"⚠️ {message}", style="bold yellow")


def print_info(message: str):
    """输出信息"""
    console.print(f"ℹ️ {message}", style="bold blue")


def create_progress(message: str) -> Progress:
    """创建进度条"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )