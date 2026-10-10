"""任务 Worker 健康检查命令.

检查任务 Worker 是否就绪，并通过退出码返回检查结果。

核心功能：
  - healthcheck_worker: 检查任务 Worker 是否就绪

使用示例：
  datamind worker healthcheck
"""

import typer


app = typer.Typer(
    help="任务 Worker 健康检查命令"
)


@app.command("healthcheck")
def healthcheck_worker() -> None:
    """检查任务 Worker 是否就绪."""
    from datamind.runtime.task_queue.healthcheck import is_worker_ready

    raise typer.Exit(0 if is_worker_ready() else 1)
