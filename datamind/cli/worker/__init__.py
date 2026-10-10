"""任务 Worker 命令.

提供批量预测和影子预测任务 Worker 的启动命令。

命令组：
  - run: 启动任务 Worker
"""

import typer

from datamind.cli.worker.run import app as run_app


app = typer.Typer(
    help="任务 Worker 命令"
)

app.add_typer(run_app)
