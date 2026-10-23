"""管理控制台健康检查命令.

检查管理控制台是否就绪，并通过退出码返回检查结果。

核心功能：
  - healthcheck_console: 检查管理控制台是否就绪

使用示例：
  datamind console healthcheck
"""

import typer

from datamind.console.healthcheck import is_console_healthy


app = typer.Typer(
    help="管理控制台健康检查命令"
)


@app.command("healthcheck")
def healthcheck_console() -> None:
    """检查管理控制台是否就绪."""
    raise typer.Exit(0 if is_console_healthy() else 1)
