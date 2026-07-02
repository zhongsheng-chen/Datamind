# datamind/cli/service/__init__.py

"""服务管理命令

提供运行时服务的生命周期管理。

命令组：
  - start: 启动服务
  - stop: 停止服务
  - restart: 重启服务
  - list: 查看服务列表
  - show: 查看服务详情
"""

from typer import Typer

from datamind.cli.service.start import app as start_app
from datamind.cli.service.stop import app as stop_app
from datamind.cli.service.restart import app as restart_app
from datamind.cli.service.list import app as list_app
from datamind.cli.service.show import app as show_app

app = Typer(help="服务管理命令")

app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(restart_app)
app.add_typer(list_app)
app.add_typer(show_app)