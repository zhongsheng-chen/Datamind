# datamind/cli/main.py

"""Datamind CLI 主入口

提供命令行工具的入口和子命令管理。

核心功能：
  - model: 模型管理子命令

使用示例：
  python -m datamind.cli.main model register \
      --name scorecard \
      --version 1.0.0 \
      --framework sklearn \
      --model-type logistic_regression \
      --task-type scoring \
      --model-path ./models/scorecard.pkl

  python -m datamind.cli.main model list --status active
"""

import typer
from importlib.metadata import version

from datamind._build import BUILD_COMMIT
from datamind.cli.model import app as model_app


def version_callback(value: bool) -> None:
    """显示版本

    参数：
        value: 是否触发版本显示
    """
    if not value:
        return

    app_version = version("datamind")

    message = f"datamind version {app_version}"

    if BUILD_COMMIT != "dev":
        message += f" (commit {BUILD_COMMIT})"

    typer.echo(message)

    raise typer.Exit()


app = typer.Typer(help="Datamind 命令行工具")


@app.callback()
def main(
    version_option: bool = typer.Option(
        False,
        "--version",
        help="显示版本信息",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Datamind CLI 主入口"""
    pass


# 注册子命令
app.add_typer(model_app, name="model")


if __name__ == "__main__":
    app()