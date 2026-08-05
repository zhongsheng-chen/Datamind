# datamind/cli/runtime/__init__.py

"""运行状态管理命令

提供部署模型期望运行状态的管理和查询功能。

命令组：
  - load: 加载部署
  - unload: 卸载部署
  - reload: 重新加载部署
  - list: 查看运行状态列表
  - show: 查看部署运行状态
"""

import typer

from datamind.cli.runtime.list import app as list_app
from datamind.cli.runtime.load import app as load_app
from datamind.cli.runtime.reload import app as reload_app
from datamind.cli.runtime.show import app as show_app
from datamind.cli.runtime.unload import app as unload_app

app = typer.Typer(
    help="运行状态管理命令"
)

app.add_typer(load_app)
app.add_typer(unload_app)
app.add_typer(reload_app)
app.add_typer(list_app)
app.add_typer(show_app)
