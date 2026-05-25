# datamind/cli/model/__init__.py

"""模型管理命令

提供模型及模型版本的管理能力。

命令组：
  - list: 列出模型
  - show: 查看模型详情
  - delete: 删除模型
  - version: 模型版本管理
"""

import typer

from datamind.cli.model.register import app as register_app
from datamind.cli.model.list import app as list_app
from datamind.cli.model.show import app as show_app
from datamind.cli.model.delete import app as delete_app


app = typer.Typer(
    help="模型管理"
)

app.add_typer(register_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(delete_app)