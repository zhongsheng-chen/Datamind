# datamind/cli/outcome/__init__.py

"""实验结果回流命令

提供业务结果回流功能。

命令组：
  - submit: 幂等提交实验结果
"""

import typer

from datamind.cli.outcome.submit import app as submit_app

app = typer.Typer(
    help="实验结果回流命令"
)

app.add_typer(submit_app)
