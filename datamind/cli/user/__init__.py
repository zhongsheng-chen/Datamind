"""用户管理命令

提供 LOCAL 用户账户的创建、查询、状态、密码和删除管理功能。

命令组：
  - create: 创建用户
  - list: 列出用户
  - show: 查看用户
  - enable: 启用用户
  - disable: 停用用户
  - reset-password: 重置用户密码
  - delete: 删除用户
"""

import typer

from datamind.cli.user.create import app as create_app
from datamind.cli.user.delete import app as delete_app
from datamind.cli.user.disable import app as disable_app
from datamind.cli.user.enable import app as enable_app
from datamind.cli.user.list import app as list_app
from datamind.cli.user.reset import app as reset_app
from datamind.cli.user.show import app as show_app


app = typer.Typer(
    help="用户管理命令"
)

app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(enable_app)
app.add_typer(disable_app)
app.add_typer(reset_app)
app.add_typer(delete_app)
