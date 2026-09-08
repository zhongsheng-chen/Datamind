"""管理控制台命令

提供内网管理控制台的启动命令。

命令组：
  - run: 启动管理控制台
"""

import typer

from datamind.cli.console.run import app as run_app


app = typer.Typer(
    help="管理控制台命令"
)

app.add_typer(
    run_app
)
