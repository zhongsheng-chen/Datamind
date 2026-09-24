"""路由管理命令.

提供模型路由规则的管理功能。

命令组：
  - create: 创建路由
  - list: 列出路由
  - show: 查看路由详情
  - enable: 启用路由
  - disable: 禁用路由
  - update: 更新路由
  - delete: 删除路由
  - restore: 恢复路由
"""

import typer

from datamind.cli.route.create import app as create_app
from datamind.cli.route.disable import app as disable_app
from datamind.cli.route.delete import app as delete_app
from datamind.cli.route.enable import app as enable_app
from datamind.cli.route.list import app as list_app
from datamind.cli.route.show import app as show_app
from datamind.cli.route.restore import app as restore_app
from datamind.cli.route.update import app as update_app

app = typer.Typer(
    help="路由管理命令"
)

app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(enable_app)
app.add_typer(disable_app)
app.add_typer(update_app)
app.add_typer(delete_app)
app.add_typer(restore_app)
