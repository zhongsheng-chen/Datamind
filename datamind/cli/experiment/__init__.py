# datamind/cli/experiment/__init__.py

"""实验管理命令

提供 A/B 实验的管理功能。

命令组：
  - create: 创建实验
  - list: 列出实验
  - show: 查看实验详情
  - start: 启动实验
  - pause: 暂停实验
  - stop: 停止实验
  - complete: 完成实验
  - archive: 归档实验
  - analyze: 分析实验效果
  - variant: 实验分组管理
"""

import typer

from datamind.cli.experiment.analyze import app as analyze_app
from datamind.cli.experiment.archive import app as archive_app
from datamind.cli.experiment.complete import app as complete_app
from datamind.cli.experiment.create import app as create_app
from datamind.cli.experiment.list import app as list_app
from datamind.cli.experiment.pause import app as pause_app
from datamind.cli.experiment.show import app as show_app
from datamind.cli.experiment.start import app as start_app
from datamind.cli.experiment.stop import app as stop_app
from datamind.cli.experiment.variant import app as variant_app

app = typer.Typer(
    help="实验管理命令"
)

app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(start_app)
app.add_typer(pause_app)
app.add_typer(stop_app)
app.add_typer(complete_app)
app.add_typer(archive_app)
app.add_typer(analyze_app)

app.add_typer(
    variant_app,
    name="variant",
    help="实验分组管理命令"
)
