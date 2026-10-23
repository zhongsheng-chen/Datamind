"""预测服务健康检查命令.

检查预测服务是否就绪，并通过退出码返回检查结果。

核心功能：
  - healthcheck_service: 检查预测服务是否就绪

使用示例：
  datamind service healthcheck
"""

import typer

from datamind.runtime.server.healthcheck import is_runtime_ready


app = typer.Typer(
    help="预测服务健康检查命令"
)


@app.command("healthcheck")
def healthcheck_service() -> None:
    """检查预测服务是否就绪."""
    raise typer.Exit(0 if is_runtime_ready() else 1)
