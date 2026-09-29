"""服务进程命令.

提供评分服务进程的启动功能。

命令组：
  - run: 启动常驻模型服务
"""

import typer

from datamind.cli.service.run import app as run_app

app = typer.Typer(
    help="服务进程命令"
)

app.add_typer(run_app)
