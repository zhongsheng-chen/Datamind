# datamind/cli/service/__init__.py

"""服务管理命令

提供运行时服务的生命周期管理。

命令组：
  - run: 启动常驻模型服务
  - load: 加载部署
  - unload: 卸载部署
  - reload: 重载部署
  - list: 查看服务列表
  - show: 查看服务详情
"""

import typer

from datamind.cli.service.list import app as list_app
from datamind.cli.service.load import app as load_app
from datamind.cli.service.reload import app as reload_app
from datamind.cli.service.run import app as run_app
from datamind.cli.service.show import app as show_app
from datamind.cli.service.unload import app as unload_app

app = typer.Typer(
    help="服务管理命令"
)

app.add_typer(run_app)
app.add_typer(load_app)
app.add_typer(unload_app)
app.add_typer(reload_app)
app.add_typer(list_app)
app.add_typer(show_app)
