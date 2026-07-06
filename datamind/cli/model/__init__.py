# datamind/cli/model/__init__.py

"""模型管理命令

提供模型及模型版本的管理功能。

命令组：
  - register: 注册模型
  - list: 列出模型
  - show: 查看模型详情
  - activate: 激活模型或模型版本
  - deactivate: 停用模型或模型版本
  - delete: 删除模型
"""

import typer

from datamind.cli.model.activate import app as activate_app
from datamind.cli.model.deactivate import app as deactivate_app
from datamind.cli.model.delete import app as delete_app
from datamind.cli.model.list import app as list_app
from datamind.cli.model.register import app as register_app
from datamind.cli.model.show import app as show_app

app = typer.Typer(
    help="模型管理命令"
)

app.add_typer(register_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(activate_app)
app.add_typer(deactivate_app)
app.add_typer(delete_app)
