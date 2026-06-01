# datamind/cli/deploy/init.py

"""部署管理命令

提供模型及模型版本的管理能力。

命令组：
  - list: 列出模型
  - show: 查看模型详情
  - delete: 删除模型
  - version: 模型版本管理
"""

import typer

from datamind.cli.deploy.create import app as create_app
from datamind.cli.deploy.enable import app as enable_app
from datamind.cli.deploy.disable import app as disable_app
from datamind.cli.deploy.list import app as list_app
from datamind.cli.deploy.show import app as show_app

app = typer.Typer(
    help="部署管理命令"
)

app.add_typer(create_app, name="create")
app.add_typer(enable_app, name="enable")
app.add_typer(disable_app, name="disable")
app.add_typer(list_app, name="list")
app.add_typer(show_app, name="show")