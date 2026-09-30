"""数据库管理命令."""

import typer

from datamind.cli.output import CLIConsole
from datamind.db import migration


app = typer.Typer(help="数据库管理")
console = CLIConsole()


@app.command("upgrade")
def upgrade() -> None:
    """将数据库升级到当前安装包的最新版本."""
    try:
        migration.upgrade_database()
    except migration.MigrationError as exc:
        console.error(str(exc))
        raise typer.Exit(code=1) from None

    console.info("数据库迁移完成")
