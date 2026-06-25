# datamind/cli/main.py

"""Datamind CLI 主入口

提供命令行工具的入口和子命令管理。

核心功能：
  - model: 模型管理子命令
  - deploy: 部署管理子命令
  - service: 服务管理子命令
  - experiment: 实验管理子命令
"""

import typer
from importlib.metadata import version

from datamind._build import BUILD_COMMIT
from datamind.cli.model import app as model_app
from datamind.cli.deploy import app as deploy_app
from datamind.cli.service import app as service_app
from datamind.cli.experiment import app as experiment_app


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
app.add_typer(deploy_app, name="deploy")
app.add_typer(service_app, name="service")
app.add_typer(experiment_app, name="experiment")


if __name__ == "__main__":
    app()