# datamind/cli/runtime/__init__.py

"""运行实例查询命令

提供运行实例查询功能。

命令组：
  - list: 查看运行状态列表
  - show: 查看部署运行状态
"""

import typer

from datamind.cli.runtime.list import app as list_app
from datamind.cli.runtime.show import app as show_app

app = typer.Typer(
    help="运行实例查询命令"
)

app.add_typer(list_app)
app.add_typer(show_app)
