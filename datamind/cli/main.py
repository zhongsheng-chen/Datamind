# datamind/cli/main.py

"""Datamind CLI 主入口

提供命令行工具的入口和子命令管理。

核心功能：
  - model: 模型管理子命令

使用示例：
  python -m datamind.cli.main model register --name scorecard --version 1.0.0 ...
  python -m datamind.cli.main model list --status active
"""

import typer

from datamind.cli.model import app as model_app

app = typer.Typer(help="Datamind 命令行工具")

# 注册子命令
app.add_typer(model_app, name="model")


if __name__ == "__main__":
    app()