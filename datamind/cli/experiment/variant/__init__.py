# datamind/cli/experiment/variant/__init__.py

"""实验分组管理命令

提供 A/B 实验分组的管理功能。

命令组：
  - add: 添加实验分组
  - update: 更新实验分组
  - list: 列出实验分组
  - show: 查看实验分组详情
  - activate: 启用实验分组
  - deactivate: 停用实验分组
  - archive: 归档实验分组
  - delete: 删除实验分组
  - restore: 恢复实验分组
"""

import typer

from datamind.cli.experiment.variant.activate import app as activate_app
from datamind.cli.experiment.variant.add import app as add_app
from datamind.cli.experiment.variant.archive import app as archive_app
from datamind.cli.experiment.variant.deactivate import app as deactivate_app
from datamind.cli.experiment.variant.delete import app as delete_app
from datamind.cli.experiment.variant.list import app as list_app
from datamind.cli.experiment.variant.show import app as show_app
from datamind.cli.experiment.variant.restore import app as restore_app
from datamind.cli.experiment.variant.update import app as update_app

app = typer.Typer(
    help="实验分组管理命令"
)

app.add_typer(add_app)
app.add_typer(update_app)
app.add_typer(list_app)
app.add_typer(show_app)
app.add_typer(activate_app)
app.add_typer(deactivate_app)
app.add_typer(archive_app)
app.add_typer(delete_app)
app.add_typer(restore_app)
