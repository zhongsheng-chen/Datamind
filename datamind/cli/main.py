# datamind/cli/main.py

"""Datamind CLI 主入口

提供命令行工具的入口和子命令管理。

核心功能：
  - init: 一次性系统初始化
  - login: 登录本地 CLI 会话
  - logout: 退出本地 CLI 会话
  - whoami: 查询当前登录身份
  - model: 模型管理子命令
  - deployment: 部署管理子命令
  - experiment: 实验管理子命令
  - route: 路由管理子命令
  - service: 服务管理子命令
  - outcome: 实验结果回流子命令
  - user: 用户管理子命令
  - role: 角色管理子命令

使用示例：
  python -m datamind.cli.main --help
"""

from importlib.metadata import version

import typer

from datamind._build import BUILD_COMMIT
from datamind.cli.auth.login import login
from datamind.cli.auth.logout import logout
from datamind.cli.auth.whoami import whoami
from datamind.cli.deployment import app as deployment_app
from datamind.cli.experiment import app as experiment_app
from datamind.cli.init import initialize
from datamind.cli.model import app as model_app
from datamind.cli.outcome import app as outcome_app
from datamind.cli.route import app as route_app
from datamind.cli.role import app as role_app
from datamind.cli.service import app as service_app
from datamind.cli.user import app as user_app
from datamind.config import get_settings
from datamind.logging import setup_logging


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


app = typer.Typer(
    help="Datamind 命令行工具",
    add_completion=False,
)


@app.callback()
def main(
        _version_option: bool = typer.Option(
            False,
            "--version",
            help="显示版本信息",
            callback=version_callback,
            is_eager=True,
        ),
) -> None:
    """Datamind CLI 主入口"""
    setup_logging(
        get_settings().logging
    )


# 注册顶层命令和子命令组
app.command("init")(
    initialize
)
app.command("login")(
    login
)
app.command("logout")(
    logout
)
app.command("whoami")(
    whoami
)
app.add_typer(model_app, name="model")
app.add_typer(deployment_app, name="deployment")
app.add_typer(experiment_app, name="experiment")
app.add_typer(route_app, name="route")
app.add_typer(service_app, name="service")
app.add_typer(outcome_app, name="outcome")
app.add_typer(user_app, name="user")
app.add_typer(role_app, name="role")

if __name__ == "__main__":
    app()
