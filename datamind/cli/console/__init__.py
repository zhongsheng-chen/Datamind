"""管理控制台命令.

提供内网管理控制台的启动命令。

命令组：
  - run: 启动管理控制台
  - healthcheck: 检查管理控制台健康状态
"""

import typer

from datamind.cli.console.healthcheck import app as healthcheck_app
from datamind.cli.console.run import app as run_app


app = typer.Typer(
    help="管理控制台命令"
)

app.add_typer(
    run_app
)

app.add_typer(
    healthcheck_app
)
