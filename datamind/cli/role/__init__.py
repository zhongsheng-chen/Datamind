# datamind/cli/role/__init__.py

"""角色管理命令

提供角色、权限和用户角色授予管理功能。

命令组：
  - create: 创建角色
  - list: 列出角色
  - show: 查看角色
  - grant: 向用户授予角色
  - revoke: 撤销用户角色
  - delete: 删除角色
"""

import typer

from datamind.cli.role.create import app as create_app
from datamind.cli.role.delete import app as delete_app
from datamind.cli.role.grant import app as grant_app
from datamind.cli.role.list import app as list_app
from datamind.cli.role.revoke import app as revoke_app
from datamind.cli.role.show import app as show_app


app = typer.Typer(
    help="角色管理命令"
)

app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(grant_app)
app.add_typer(revoke_app)
app.add_typer(delete_app)
