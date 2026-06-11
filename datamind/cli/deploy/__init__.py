# datamind/cli/deploy/_init_.py

"""部署管理命令

提供模型部署生命周期的管理功能。

命令组：
  - create: 创建模型部署
  - enable: 启用部署
  - disable: 停用部署
  - list: 列出部署
  - show: 查看部署详情
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

app.add_typer(create_app)
app.add_typer(enable_app)
app.add_typer(disable_app)
app.add_typer(list_app)
app.add_typer(show_app)