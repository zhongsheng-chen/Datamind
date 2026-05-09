# datamind/cli/main.py

"""Datamind CLI"""

import typer

from datamind.cli.model import app as model_app

app = typer.Typer(
    help="Datamind Machine Learning Platform CLI"
)

# 注册子命令
app.add_typer(
    model_app,
    name="model",
)


if __name__ == "__main__":
    app()